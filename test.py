from g4f.client import Client

client = Client()
response = client.images.generate(
    model="dalle-3",  # Other models: 'dalle-3', 'gpt-image', etc.
    prompt="Милый котёнок спокойно спит под пледом, лунный свет из окна, случайный предмет с текстом Волки МИРЭА или РТУ МИРЭА или Волки РТУ МИРЭА. Без логотипов, только текст ",
    response_format="url"
)
print(f"Generated image URL: {response.data[0].url}")