import os
from dotenv import load_dotenv
from groq import Groq

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../../"))
filePath = os.path.join(project_root, "scripts", "wordsSeach", "Ilat", "ilat.txt")

load_dotenv()
apiKey = Groq(api_key=os.environ.get('GROQ_API_KEY'))
if not apiKey:
    raise ValueError('API Key not set')
client = Groq(api_key=os.environ.get('GROQ_API_KEY'))

def callAPI(productTitle):
    print("BVien dans ce fichier")
    with open(filePath, "r", encoding="utf-8") as f:
        dataForIA = f.read()

    prompt = f"""
    {dataForIA}
    Produit: {productTitle}
    Réponse:
    """

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    print("word", response.choices[0].message.content)
    return response.choices[0].message.content
