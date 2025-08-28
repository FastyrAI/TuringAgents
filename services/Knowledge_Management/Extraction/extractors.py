import spacy
import json
from typing import List, Dict, Any
from config import ALLOWED_ENTITY_TYPES, MIN_ENTITY_LENGTH, MIN_CONCEPT_LENGTH, MAX_ENTITIES_PER_DOC, MAX_CONCEPTS_PER_DOC, IGNORE_WORDS, ENTITY_TYPE_PRIORITY, ENABLE_SVO_RELATIONS, ENABLE_COOCCURRENCE_RELATIONS, MAX_RELATIONS_PER_DOC, GEMINI_API_KEY, GEMINI_MODEL, ENABLE_GEMINI_EXTRACTION


class GeminiProcessor:
    def __init__(self):
        """Initialize Gemini processor"""
        if not GEMINI_API_KEY:
            print("Warning: GEMINI_API_KEY not set. Gemini extraction will be disabled.")
            self.enabled = False
            return
            
        try:
            import google.generativeai as genai
            genai.configure(api_key=GEMINI_API_KEY)
            self.model = genai.GenerativeModel(GEMINI_MODEL)
            self.enabled = True
        except ImportError:
            print("Warning: google-generativeai not installed. Gemini extraction will be disabled.")
            self.enabled = False
        except Exception as e:
            print(f"Error initializing Gemini: {e}")
            self.enabled = False
    
    def extract_entities_and_relations(self, content: str, message_id: str) -> List[Dict[str, Any]]:
        """Extract entities and relations using Gemini LLM"""
        if not self.enabled or not ENABLE_GEMINI_EXTRACTION:
            return []
            
        queries = []
        
        try:
            # Create prompt for entity and relation extraction
            prompt = f"""
            Extract entities and relationships from the following text. Focus on creating MEANINGFUL RELATIONSHIPS between entities rather than just identifying entities. Return the result as a JSON object with this exact structure:
            {{
                "entities": [
                    {{"text": "entity name", "type": "PERSON|ORG|GPE|PRODUCT|EVENT|WORK_OF_ART|LAW|LANGUAGE|CONCEPT"}}
                ],
                "relations": [
                    {{"subject": "entity1", "predicate": "relationship", "object": "entity2"}}
                ]
            }}
            
            Text: {content}
            
            Guidelines:
            - Extract only meaningful entities (names, organizations, places, products, events, etc.)
            - PRIORITY: Focus on creating specific, meaningful relationships between entities
            - Use specific, descriptive relationship types. Common examples:
              * Employment: "WORKS_FOR", "EMPLOYED_BY", "CEO_OF", "DIRECTOR_OF", "MANAGER_OF", "EMPLOYEE_OF"
              * Location: "LOCATED_IN", "BASED_IN", "HEADQUARTERED_IN", "LIVES_IN", "BORN_IN", "DIED_IN"
              * Ownership: "OWNS", "FOUNDED", "CREATED", "ESTABLISHED", "BUILT", "DEVELOPED"
              * Membership: "MEMBER_OF", "PART_OF", "BELONGS_TO", "AFFILIATED_WITH", "ASSOCIATED_WITH"
              * Education: "STUDIED_AT", "GRADUATED_FROM", "ATTENDED", "ALUMNI_OF", "PROFESSOR_AT"
              * Family: "MARRIED_TO", "PARENT_OF", "CHILD_OF", "SIBLING_OF", "SPOUSE_OF"
              * Business: "ACQUIRED_BY", "MERGED_WITH", "COMPETES_WITH", "SUPPLIES_TO", "DISTRIBUTES_TO"
              * Creative: "AUTHOR_OF", "DIRECTOR_OF", "PRODUCER_OF", "COMPOSER_OF", "ARTIST_OF"
              * Temporal: "HAPPENED_DURING", "OCCURRED_IN", "TOOK_PLACE_IN", "STARTED_IN", "ENDED_IN"
              * Financial: "INVESTED_IN", "FUNDED_BY", "PARTNERED_WITH", "COLLABORATED_WITH"
              * Technology: "DEVELOPED_BY", "USES_TECHNOLOGY", "INTEGRATES_WITH", "COMPATIBLE_WITH"
              * Communication: "MENTIONS", "REFERENCES", "DISCUSSES", "ANALYZES", "REPORTS_ON"
              * Events: "PARTICIPATED_IN", "ORGANIZED", "SPONSORED", "HOSTED", "ATTENDED"
              * Products: "MANUFACTURES", "SELLS", "DISTRIBUTES", "SUPPORTS", "COMPETES_WITH"
            - IMPORTANT: Make sure both subject and object entities exist in the entities list
            - Only create relationships between entities that are actually mentioned in the text
            - Be specific and avoid generic relationships like "related to" or "connected to"
            - Use UPPERCASE relationship names for consistency
            - Focus on the most important relationships that add value to the knowledge graph
            - Keep entities and relations concise and relevant
            - Return valid JSON only
            
            Example:
            If text mentions "John Smith works as CEO for Microsoft in Seattle", extract:
            - entities: [{{"text": "John Smith", "type": "PERSON"}}, {{"text": "Microsoft", "type": "ORG"}}, {{"text": "Seattle", "type": "GPE"}}]
            - relations: [
                {{"subject": "John Smith", "predicate": "CEO_OF", "object": "Microsoft"}},
                {{"subject": "Microsoft", "predicate": "HEADQUARTERED_IN", "object": "Seattle"}}
            ]
            """
            
            response = self.model.generate_content(prompt)
            result_text = response.text.strip()
            
            # Parse JSON response
            try:
                result = json.loads(result_text)
            except json.JSONDecodeError:
                # Try to extract JSON from response if it's wrapped in markdown
                if "```json" in result_text:
                    json_start = result_text.find("```json") + 7
                    json_end = result_text.find("```", json_start)
                    if json_end != -1:
                        result = json.loads(result_text[json_start:json_end].strip())
                    else:
                        return []
                else:
                    return []
            
            # Process entities first and track them
            extracted_entities = set()
            if "entities" in result:
                for entity in result["entities"][:MAX_ENTITIES_PER_DOC]:
                    if "text" in entity and "type" in entity:
                        entity_text = entity["text"].strip()
                        entity_type = entity["type"].strip()
                        
                        # Basic filtering
                        if len(entity_text) < MIN_ENTITY_LENGTH:
                            continue
                        if entity_text.lower() in IGNORE_WORDS:
                            continue
                        
                        extracted_entities.add(entity_text)
                        
                        # Create entity node
                        entity_query = f"""
                        MERGE (e:Entity {{id: '{entity_text.lower().replace(" ", "_")}', text: '{entity_text}', type: '{entity_type}', source_message: '{message_id}'}})
                        """
                        queries.append({"query": entity_query})
                        

            
            # Process relations - only create relationships between entities that exist
            if "relations" in result:
                for relation in result["relations"][:MAX_RELATIONS_PER_DOC]:
                    if "subject" in relation and "predicate" in relation and "object" in relation:
                        subject = relation["subject"].strip()
                        predicate = relation["predicate"].strip()
                        obj = relation["object"].strip()
                        
                        # Only create relationship if both entities exist
                        if subject in extracted_entities and obj in extracted_entities:
                            
                            clean_predicate = predicate.replace(" ", "_").replace("-", "_").replace("'", "").replace('"', "").upper()
                            
                            # Create connections from message to both subject and object entities
                            # This allows clicking on messages to see all related entities
                            subject_link_query = f"""
                            MATCH (m:Message {{id: '{message_id}'}})
                            MATCH (s:Entity {{text: '{subject}', source_message: '{message_id}'}})
                            WITH m, s
                            MERGE (m)-[:EXTRACTED]->(s)
                            """
                            queries.append({"query": subject_link_query})
                            
                            obj_link_query = f"""
                            MATCH (m:Message {{id: '{message_id}'}})
                            MATCH (o:Entity {{text: '{obj}', source_message: '{message_id}'}})
                            WITH m, o
                            MERGE (m)-[:EXTRACTED]->(o)
                            """
                            queries.append({"query": obj_link_query})
                            
                            # Create the actual semantic relationship from subject to object
                            relation_query = f"""
                            MATCH (s:Entity {{text: '{subject}', source_message: '{message_id}'}})
                            MATCH (o:Entity {{text: '{obj}', source_message: '{message_id}'}})
                            WITH s, o
                            CREATE (s)-[r:{clean_predicate} {{source_message: '{message_id}'}}]->(o)
                            """
                            queries.append({"query": relation_query})
                            
                            # print(f"Created relationship: {subject} --[{clean_predicate}]--> {obj}")
                        else:
                            print(f"Gemini skipped relationship: {subject} --[{predicate}]--> {obj} (entities not found)")
                        
        except Exception as e:
            print(f"Error in Gemini extraction: {e}")
            return []
        
        return queries
