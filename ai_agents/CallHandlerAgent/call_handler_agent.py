from flask import Flask, request
from twilio.twiml.voice_response import VoiceResponse

# To make this script functional, you would need to:
# 1. Install the necessary libraries: pip install Flask twilio
# 2. Get a Twilio account, a Twilio phone number, and your account credentials.
# 3. Use a tool like ngrok to expose your local server to the internet, so Twilio can send it requests.
# 4. Configure your Twilio phone number's voice webhook to point to your ngrok URL (e.g., https://your-ngrok-url.ngrok.io/voice).

app = Flask(__name__)

@app.route("/voice", methods=['GET', 'POST'])
def voice():
    """Respond to incoming phone calls with a brief message."""
    # Start our TwiML response. TwiML is a set of instructions you can use to tell Twilio what to do when you receive an incoming call.
    resp = VoiceResponse()

    # Greet the caller with a synthesized voice.
    resp.say("Hello, you have reached the Rebusiness Automation Project. Please leave a message after the beep, and we will get back to you shortly.", voice='alice')

    # Record the caller's message. Twilio can automatically transcribe the recording for you.
    resp.record(transcribe=True, transcribe_callback='/handle-transcription')

    # End the call.
    resp.hangup()

    return str(resp)

@app.route("/handle-transcription", methods=['POST'])
def handle_transcription():
    """
    This endpoint receives the transcription of the recorded message from Twilio.
    """
    # Get the transcription text from the Twilio request.
    transcription_text = request.form['TranscriptionText']

    # In a real implementation, you would take this transcription and:
    # 1. Use a large language model to understand the caller's intent.
    # 2. Generate a response.
    # 3. Trigger other actions, like sending an email to a human or adding the message to a CRM.
    print("--- New Voicemail Received ---")
    print(f"Caller's message: {transcription_text}")
    print("----------------------------")

    # We must return a 200 OK response to Twilio to acknowledge receipt of the transcription.
    return "OK", 200

if __name__ == "__main__":
    # --- IMPORTANT ---
    # To get this agent working, you need to:
    # 1. Run this script: python ai_agents/CallHandlerAgent/call_handler_agent.py
    # 2. In a separate terminal, run ngrok to expose this server to the internet: ngrok http 5000
    # 3. Take the public URL provided by ngrok and set it as the voice webhook for your Twilio phone number in the Twilio console.
    print("Starting the Call Handler Agent...")
    print("This agent runs a web server on port 5000.")
    print("Use a tool like ngrok to expose this port to the internet.")
    app.run(port=5000, debug=True)
