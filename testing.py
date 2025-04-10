# from langchain_ollama.llms import OllamaLLM

# llm = OllamaLLM(model="llama3.1", base_url="http://localhost:11434")
# try:
#     response = llm.invoke("Hello, can you respond?")
#     print(response)
# except Exception as e:
#     print(f"Error: {e}")

#     AIzaSyD2p3QL6vI6614gZ_u6epfa5z9KBh8x7Yo

#     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

# AIzaSyDMwVI8kjqiKoFdTncQ2wO2R14UffO3EfY

# import requests
# import json

# response = requests.get(
#   url="https://openrouter.ai/api/v1/auth/key",
#   headers={
#     "Authorization": f"Bearer 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"
#   }
# )

# # print(json.dumps(response.json(), indent=2))
# import requests
# import json

# response = requests.post(
#   url="https://openrouter.ai/api/v1/chat/completions",
#   headers={
#     "Authorization": "Bearer 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",
#     # "HTTP-Referer": "<YOUR_SITE_URL>", # Optional. Site URL for rankings on openrouter.ai.
#     # "X-Title": "<YOUR_SITE_NAME>", # Optional. Site title for rankings on openrouter.ai.
#   },
#   data=json.dumps({
#     "model": "google/gemini-2.5-pro-exp-03-25:free", # Optional
#     "messages": [
#       {
#         "role": "user",
#         "content": "What is the meaning of life?"
#       }
#     ]
#   })
# )
