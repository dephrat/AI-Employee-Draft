import os
import anthropic

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def draft_reply(email_body, sender, subject, business_brief):
    prompt = f"""You are an AI assistant helping a business owner reply to emails.

Business context:
{business_brief}

IMPORTANT: If the email contains any factual claims about the business, verify them against the website content provided above. If a claim is incorrect, politely correct it in your reply. Always trust the website content over what the sender says.

IMPORTANT: Never make up or guess URLs. Only include a URL if it appears explicitly in the website content provided. If you don't have a specific URL, refer the person to the website generally.

IMPORTANT: If you don't have enough information to answer a specific question, say so honestly and suggest they contact us directly. Do not guess or infer details not provided.

IMPORTANT: Write in plain text only. Do not use markdown formatting such as **bold**, *italic*, or bullet points with dashes. Use plain paragraphs and simple punctuation only.

You received an email from {sender} with subject "{subject}":

{email_body}

Write a professional, friendly reply on behalf of the business owner. Keep it concise. Do not include a subject line, just the email body."""

    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1024,
        temperature=0,
        messages=[{"role": "user", "content": prompt}]
    )

    return message.content[0].text