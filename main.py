from flask import Flask, request, render_template, send_from_directory
from openai import OpenAI
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
import json
import logging
import os
import requests
import tempfile

app = Flask(__name__)
aiClient = OpenAI()

logging.basicConfig(level=logging.INFO)
logging.info('setup the server')


@app.route('/')
def index():
  return render_template('index.html')


@app.route('/mp3/<filename>')
def serve_mp3(filename):
  return send_from_directory('static', filename)


# Attempting webhook for conversations
@app.route('/bot2', methods=['POST'])
def bot2():
  # prepare the incoming conversation
  incoming_msg = request.values.get('Body', '').lower()
  incoming_conversation = request.values.get('ConversationSid', '')
  incoming_sender = os.environ['TWILIO_FROM_NUMBER']

  # Find your Account SID and Auth Token at twilio.com/console
  # and set the environment variables. See http://twil.io/secure
  account_sid = os.environ['TWILIO_SID']
  auth_token = os.environ['TWILIO_AUTH_TOKEN']
  client = Client(account_sid, auth_token)

  # Look for texts that start with gpt and respond with gpt
  if incoming_msg.startswith('gpt'):
    logging.info(f'Responding with gpt!')

    # return a chatgpt response
    completion = aiClient.chat.completions.create(model="gpt-3.5-turbo",
                                                  messages=[{
                                                      "role":
                                                      "user",
                                                      "content":
                                                      incoming_msg
                                                  }],
                                                  temperature=0.1)
    answer = str(completion.choices[0].message.content)

    message = client.conversations \
      .v1 \
      .conversations(incoming_conversation) \
      .messages \
      .create(
         author="+14069465477",
         body=answer
      )
  # Look for texts that start with audio and respond with audio using eleven labs
  elif incoming_msg.startswith('audio'):
    logging.info(f'Request for Audio')
    CHUNK_SIZE = 1024
    VOICE_ID = "21m00Tcm4TlvDq8ikWAM"
    TTS_URL = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}/stream"

    message = client.conversations \
      .v1 \
      .conversations(incoming_conversation) \
      .messages \
      .create(
         author="+14069465477",
         body="Got it, I'll get back to you shortly",
      )

    headers = {
        "Accept": "audio/mpeg",
        "xi-api-key": os.environ['ELEVEN_LABS_API_KEY'],
    }

    data = {
        "text": incoming_msg,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "similarity_boost": 0.8,
            "stability": 0.5,
            "style": 0,
            "use_speaker_boost": True
        }
    }

    response = requests.post(TTS_URL, headers=headers, json=data, stream=True)

    if response.ok:
      logging.info('request for audio was successful')

      # Open the output file in write-binary mode
      OUTPUT_PATH = os.path.join(
          app.static_folder,
          f"output.mp3")  # Path to save the output audio file
      with open(OUTPUT_PATH, "wb") as f:
        # Read the response in chunks and write to the file
        for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
          f.write(chunk)
      # Inform the user of success
      logging.info("Audio stream saved successfully.")

      # Save audio file locally
      # with tempfile.NamedTemporaryFile(delete=False) as temp_audio_file:
      #   temp_audio_file.write(response.content)
      #   temp_audio_file_path = temp_audio_file.name

      audio_message = client.conversations \
        .v1 \
        .conversations(incoming_conversation) \
        .messages \
        .create(
           author="+14069465477",
           body=f"Here's the audio: {OUTPUT_PATH}",
        )

      # Clean up temporary audio file
      # os.unlink(temp_audio_file_path)
    else:
      logging.info('request for audio failed')
  else:
    logging.info(f'Not responding to message')
  return "Ok"


if __name__ == '__main__':
  app.run(host='0.0.0.0', port=8080)
