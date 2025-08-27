import spacy
from typing import List, Dict, Any
from config import ALLOWED_ENTITY_TYPES, MIN_ENTITY_LENGTH, MIN_CONCEPT_LENGTH, MAX_ENTITIES_PER_DOC, MAX_CONCEPTS_PER_DOC, IGNORE_WORDS, ENTITY_TYPE_PRIORITY, ENABLE_SVO_RELATIONS, ENABLE_COOCCURRENCE_RELATIONS, MAX_RELATIONS_PER_DOC

class NLPProcessor:
    def __init__(self, model_name: str):
        """Initialize NLP processor with spaCy model"""
        try:
            self.nlp = spacy.load(model_name)
        except OSError:
            # If model not found, download it
            spacy.cli.download(model_name)
            self.nlp = spacy.load(model_name)
    
    def extract_entities_and_relations(self, content: str, message_id: str) -> List[Dict[str, Any]]:
        """Extract entities and relations from text content with simple filtering"""
        queries = []
        
        try:
            # Process the text with spaCy
            doc = self.nlp(content)
        except Exception as e:
            print(f"Error processing text with spaCy: {e}")
            return queries
        
        # Extract named entities with filtering and deduplication
        entities = []
        entity_map = {}  # Track entities by text to handle type conflicts
        
        for ent in doc.ents:
            try:
                # Apply simple filters
                if len(ent.text) < MIN_ENTITY_LENGTH:
                    continue
                    
                if ALLOWED_ENTITY_TYPES and ent.label_ not in ALLOWED_ENTITY_TYPES:
                    continue
                
                # Skip if entity is just common words
                entity_words = ent.text.lower().split()
                if len(entity_words) == 1 and entity_words[0] in IGNORE_WORDS:
                    continue
                
                # Handle entity type conflicts by keeping the highest priority type
                entity_key = ent.text.lower().strip()
                if entity_key in entity_map:
                    existing_entity = entity_map[entity_key]
                    existing_priority = ENTITY_TYPE_PRIORITY.get(existing_entity["label"], 999)
                    current_priority = ENTITY_TYPE_PRIORITY.get(ent.label_, 999)
                    
                    # Keep the entity with higher priority (lower number)
                    if current_priority >= existing_priority:
                        continue
                    else:
                        # Replace with higher priority entity
                        entities.remove(existing_entity)
                
                if len(entities) >= MAX_ENTITIES_PER_DOC:
                    break
                
                entity_data = {
                    "text": ent.text,
                    "label": ent.label_,
                    "start": ent.start_char,
                    "end": ent.end_char
                }
                
                entities.append(entity_data)
                entity_map[entity_key] = entity_data
                
                # Create entity node with unique ID based on text only (not type)
                entity_query = f"""
                MERGE (e:Entity {{id: '{ent.text.lower().replace(" ", "_")}', text: '{ent.text}', type: '{ent.label_}', source_message: '{message_id}'}})
                """
                queries.append({"query": entity_query})
            except Exception as e:
                print(f"Error processing entity {ent.text}: {e}")
                continue
        
        # Extract noun chunks as concepts with filtering
        concepts = []
        for chunk in doc.noun_chunks:
            if len(concepts) >= MAX_CONCEPTS_PER_DOC:
                break
                
            chunk_text = chunk.text.strip()
            if chunk_text and len(chunk_text) >= MIN_CONCEPT_LENGTH:
                # Skip if chunk starts with common words
                chunk_words = chunk_text.lower().split()
                if chunk_words[0] in IGNORE_WORDS:
                    continue
                
                # Skip if chunk is just common words
                if len(chunk_words) == 1 and chunk_words[0] in IGNORE_WORDS:
                    continue
                
                # Skip if chunk is too generic
                if chunk_text.lower() in ["this", "that", "these", "those", "it", "they", "them", "we", "us", "you"]:
                    continue
                
                concepts.append({
                    "text": chunk_text,
                    "root": chunk.root.text
                })
                
                # Create concept node
                concept_query = f"""
                MERGE (c:Concept {{id: '{chunk_text.lower().replace(" ", "_")}', text: '{chunk_text}', root: '{chunk.root.text}', source_message: '{message_id}'}})
                """
                queries.append({"query": concept_query})
        
        # Extract relationships between entities
        stored_entity_texts = {entity["text"] for entity in entities}
        relations = []
        
        # Method 1: Subject-verb-object patterns
        if ENABLE_SVO_RELATIONS:
            for token in doc:
                if token.dep_ == "ROOT" and token.pos_ == "VERB":
                    # Find subject and object
                    subject = None
                    obj = None
                    
                    for child in token.children:
                        if child.dep_ in ["nsubj", "nsubjpass"]:
                            subject = child.text
                        elif child.dep_ in ["dobj", "pobj"]:
                            obj = child.text
                    
                    # Only create relations if both subject and object are stored entities
                    if subject and obj and subject in stored_entity_texts and obj in stored_entity_texts:
                        relations.append({
                            "subject": subject,
                            "predicate": token.text,
                            "object": obj
                        })
        
        # Method 2: Co-occurrence relationships (entities mentioned in same sentence)
        if ENABLE_COOCCURRENCE_RELATIONS:
            for sent in doc.sents:
                sent_entities = []
                for ent in sent.ents:
                    if ent.text in stored_entity_texts:
                        sent_entities.append(ent.text)
                
                # Create relationships between entities in the same sentence
                for i in range(len(sent_entities)):
                    for j in range(i + 1, len(sent_entities)):
                        if sent_entities[i] != sent_entities[j]:
                            relations.append({
                                "subject": sent_entities[i],
                                "predicate": "co_occurs_with",
                                "object": sent_entities[j]
                            })
        
        # Limit the number of relations to avoid graph explosion
        if len(relations) > MAX_RELATIONS_PER_DOC:
            relations = relations[:MAX_RELATIONS_PER_DOC]
        
        # Create relationships in separate queries
        for relation in relations:
            relation_query = f"""
            MATCH (s:Entity {{text: '{relation['subject']}', source_message: '{message_id}'}})
            MATCH (o:Entity {{text: '{relation['object']}', source_message: '{message_id}'}})
            WITH s, o
            CREATE (s)-[r:RELATES {{predicate: '{relation['predicate']}', source_message: '{message_id}'}}]->(o)
            """
            queries.append({"query": relation_query})
        
        # Link message to extracted entities and concepts
        for entity in entities:
            link_query = f"""
            MATCH (m:Message {{id: '{message_id}'}})
            MATCH (e:Entity {{text: '{entity['text']}', source_message: '{message_id}'}})
            WITH m, e
            CREATE (m)-[:CONTAINS]->(e)
            """
            queries.append({"query": link_query})
        
        for concept in concepts:
            link_query = f"""
            MATCH (m:Message {{id: '{message_id}'}})
            MATCH (c:Concept {{text: '{concept['text']}', source_message: '{message_id}'}})
            WITH m, c
            CREATE (m)-[:CONTAINS]->(c)
            """
            queries.append({"query": link_query})
        
        return queries
