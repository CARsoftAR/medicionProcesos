import google.generativeai as genai
import os
import sys

def test_gemini():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: No GEMINI_API_KEY in environment")
        return
    
    print(f"Testing Gemini with key: {api_key[:5]}...")
    genai.configure(api_key=api_key)
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content("Responde 'OK' si recibes este mensaje.")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Gemini Test Failed: {e}")

if __name__ == "__main__":
    test_gemini()
