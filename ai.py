import os
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def draft_reply(email_body, sender, subject, business_brief):
    prompt = f"""You are an AI assistant helping a business owner reply to emails.

Business context:
{business_brief}

You received an email from {sender} with subject "{subject}":

{email_body}

Write a professional, friendly reply on behalf of the business owner. Keep it concise. Do not include a subject line, just the email body."""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=300
    )

    return response.choices[0].message.content