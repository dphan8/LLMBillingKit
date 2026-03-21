from openai import OpenAI
from LLMBillingKit import track

client = OpenAI()
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Say hello"}]
)

result = track(response, charged=0.01, customer="test_user")
print(result)
