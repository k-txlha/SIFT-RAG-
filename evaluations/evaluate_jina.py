from backend.jina_embedding import embed_documents, embed_query

document_vector = embed_documents(["ISO 27001 defines requirements for an ISMS."])[0]
query_vector = embed_query("What is an ISMS?")

print("Document dimensions:", len(document_vector))
print("Query dimensions:", len(query_vector))