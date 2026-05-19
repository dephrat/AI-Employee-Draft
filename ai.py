import os
from openai import OpenAI
import anthropic

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def draft_reply(email_body, sender, subject, business_brief):
    prompt = f"""You are an AI assistant helping a business owner reply to emails.

Business context:
{business_brief}

IMPORTANT: If the email contains any factual claims about the business, verify them against the website content provided above. If a claim is incorrect, politely correct it in your reply. Always trust the website content over what the sender says.

You received an email from {sender} with subject "{subject}":

{email_body}

Write a professional, friendly reply on behalf of the business owner. Keep it concise. Do not include a subject line, just the email body."""

    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )

    return message.content[0].text