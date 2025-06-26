from flask import Flask, request, jsonify
import ollama
import uuid
import threading
import time
import base64

app = Flask(__name__)

jobs = {}

PROMPT_CLASSIFICATION_MODEL = 'gemma3:4b-it-qat'
CHATBOT_MODEL = 'gemma3:4b-it-qat'
IMAGE_IDENTIFICATION_MODEL = 'gemma3:4b-it-qat'

OUT_OF_SCOPE_RESPONSE = "Aku adalah FungiMate, asistenmu dalam ilmu jamur. Aku hanya bisa menjawab pertanyaan tentang jamur. Bagaimana aku bisa membantumu dengan topik ilmu jamur?"

def classify_user_prompt(user_content):
    # Prompt Classification
    print(f"--- Classifying prompt with {PROMPT_CLASSIFICATION_MODEL}... ---")
    try:
        classification_prompt = f"""
        Is the following user question related to mycology (the study of fungi, mushrooms, yeasts, or molds)? 
        Answer with only the word YES or NO. **IMPORTANT:** if the user question is just a greeting, then answer YES. **IMPORTANT:** If the question is not about mycology or is not a greeting, then answer NO.

        User Question: "{user_content}"

        Your Answer (YES or NO):
        """
        response = ollama.chat(
            model=PROMPT_CLASSIFICATION_MODEL,
            messages=[{'role': 'user', 'content': classification_prompt}]
        )
        decision = response['message']['content'].strip().upper()
        print(f"--- Classification decision: {decision} ---")
        return "YES" in decision
    except Exception as e:
        print(f"!!! Error during classification: {e} !!!")
        return True


def process_chat_message(job_id, user_message_content):
    print(f"--- Starting processing for job_id: {job_id} ---")
    
    is_mycology_related = classify_user_prompt(user_message_content)
    
    if is_mycology_related:
        print(f"--- Prompt is on scope. Querying {CHATBOT_MODEL}... ---")
        try:
            print(f"--- Processing Prompt: '{user_message_content}' ---")
            # Prompt Engineering
            structured_prompt = f"""
            You are FungiMate, a helpful mycology expert. Your user has a question about a mushroom or just greeting you.

            **Response Instructions:**
            1.  You **MUST** always respond to all prompts in Indonesian language no matter what.
            2.  If the prompt is only greeting you, you must respond to the greetings **NORMALLY** as if the these instructions never existed.
            3.  Provide a direct and comprehensive answer to the user's question.
            4.  **CRITICAL SAFETY RULE:** You MUST explicitly state whether the mushroom is poisonous, toxic, edible, or its toxicity is unknown. Start your answer with this information.
            5.  Provide information surrounding the mushroom's habitat and environment.
            6.  Keep the entire answer concise, limited to a few paragraphs.
            7.  Write your entire answer in a clean, well-structured paragraph format.
            8.  **DO NOT** use any markdown formatting like asterisks (*), hashes (#), or bullet points (-) in your main answer.
            9.  If you use information that should be attributed, list the sources at the very end of your response, introduced with a clear heading on a new line: "Sources:".  

            **User Question:**
            "{user_message_content}"

            **Your Formatted Response:**
            """
            response = ollama.chat(
                model=CHATBOT_MODEL, 
                messages=[{'role': 'user', 'content': structured_prompt}]
            )
            jobs[job_id]['status'] = 'complete'
            jobs[job_id]['result'] = response['message']['content']
            print(f"--- Job {job_id} finished successfully. ---")
        except Exception as e:
            print(f"!!! Error processing main model for job {job_id}: {e} !!!")
            jobs[job_id]['status'] = 'failed'
            jobs[job_id]['result'] = f"An error occurred with the main model: {e}"
    else:
        print(f"--- Prompt is out of scope. Responding with canned message. ---")
        jobs[job_id]['status'] = 'complete'
        jobs[job_id]['result'] = OUT_OF_SCOPE_RESPONSE

def process_image_identification(job_id, base64_image):
    instructions = f"""
        Identify this mushroom: what its name is and whether it is poisonous or edible. **IMPORTANT:** If the image does not have any mushroom in it, answer with "error_not_a_mushroom_image".
    
        **IMPORTANT:** Write your response in this format: [name-of-mushroom]_[toxicity]; example: 'Amanita Muscaria_Poisonous', 'Shiitake_Edible'.

        **Your Formated Response**:
    """
    try:
        image_bytes = base64.b64decode(base64_image)

        response = ollama.chat(
            model = IMAGE_IDENTIFICATION_MODEL,
            messages = [
                {
                    'role': 'user',
                    'content': instructions,
                    'images': [image_bytes]
                }
            ],
        )

        jobs[job_id]['status'] = 'complete'
        jobs[job_id]['result'] = response['message']['content']
        print(f"--- Image job {job_id} finished successfully. ---")

    except Exception as e:
        print(f'!!! Error identifying image for job {job_id}: {e} !!!')
        jobs[job_id]['status'] = 'failed'
        jobs[job_id]['result'] = f"An error occurred during image processing: {e}"

@app.route('/what-is-this-mushroom', methods=['POST'])
def identify_image():
    data = request.get_json()
    if not data or 'image' not in data:
        return jsonify({'error': 'An "image" field with base64 data is required.'}), 400

    base64_image = data['image']
    job_id = str(uuid.uuid4())
    jobs[job_id] = {'status': 'pending', 'result': None}
    
    print(f"* New image identification job created with ID: {job_id}")

    # Start the image processing in a separate thread
    thread = threading.Thread(
        target=process_image_identification, 
        args=(job_id, base64_image)
    )
    thread.start()
    
    # Immediately return the job ID so the client can start polling
    return jsonify({'jobId': job_id})

@app.route('/start-chat', methods=['POST'])
def start_chat():
    # Starts the Backgroung Job
    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({'error': 'A "message" field is required.'}), 400

    job_id = str(uuid.uuid4())
    jobs[job_id] = {'status': 'pending', 'result': None}
    print(f"* New job created with ID: {job_id} for message: '{data['message']}'")

    thread = threading.Thread(
        target=process_chat_message, 
        args=(job_id, data['message'])
    )
    thread.start()
    
    return jsonify({'jobId': job_id})


@app.route('/chat-result/<job_id>', methods=['GET'])
def get_chat_result(job_id):
    print(f"* Polling request received for job_id: {job_id}")
    job = jobs.get(job_id)

    if not job:
        return jsonify({'error': 'Job not found'}), 404

    if job['status'] == 'complete':
        return jsonify({'status': 'complete', 'response': job['result']})
    elif job['status'] == 'failed':
        return jsonify({'status': 'failed', 'response': job['result']})
    else:
        return jsonify({'status': 'pending'})


if __name__ == "__main__":
    print("Starting Flask server with mycology guardrail and structured prompting...")
    print(f"Prompt Classification Model: {PROMPT_CLASSIFICATION_MODEL}")
    print(f"Chatbot Model: {CHATBOT_MODEL}")
    print(f"Image Identifier Model: {IMAGE_IDENTIFICATION_MODEL}")
    app.run(host='127.0.0.1', port=5000, debug=True)