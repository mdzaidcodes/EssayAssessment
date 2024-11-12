from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
import ollama
import re
import traceback

app = Flask(__name__)
socketio = SocketIO(app)

# Load the Llama model for response generation
model_name = 'llama3.1'
try:
    ollama.pull(model_name)
except Exception as e:
    print(f"Error preloading model '{model_name}': {e}")

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('evaluate_essay')
def handle_evaluation(data):
    # Extract topic and essay text from the request data
    topic = data.get('topic', '').strip()
    essay = data.get('essay', '').strip()

    if not topic or not essay:
        emit('evaluation', {'text': "Please provide both a topic and an essay for evaluation."})
        return

    # Define the prompt for evaluation
    prompt = (
        f"As an AI teaching assistant, evaluate the following essay based on these criteria:\n\n"
        f"1. Critical Thinking: Does the essay demonstrate a deep understanding and analysis of the topic? Provide a two-sentence remark.\n"
        f"2. Clarity: Is the essay clearly written and easy to understand? Provide a two-sentence remark.\n"
        f"3. Application: Does the essay apply relevant concepts or theories effectively? Provide a two-sentence remark.\n"
        f"4. Understanding: Does the essay show a solid understanding of the topic? Provide a two-sentence remark.\n"
        f"5. Creativity: Is there originality and creativity in how the essay addresses the topic? Provide a two-sentence remark.\n\n"
        f"--- Essay Topic ---\n{topic}\n\n"
        f"--- Essay Text ---\n{essay}\n\n"
        f"Please provide feedback and a score (out of 10) for each criterion, followed by an overall impression and suggestions for improvement."
    )

    try:
        response = ollama.chat(
            model=model_name,
            messages=[
                {'role': 'system', 'content': prompt},
                {'role': 'user', 'content': "Evaluate the essay provided above based on the specified criteria."}
            ],
        )

        # Extract the generated evaluation content and clean it
        evaluation_content = response['message']['content']
        
        # Remove double asterisks
        evaluation_content = evaluation_content.replace("**", "")
        
        # Replace single asterisks with line breaks
        evaluation_content = evaluation_content.replace("*", "<br>")

        # Parsing the response
        evaluation_data = {}
        
        # Define the criteria to look for in the response
        criteria = ["Critical Thinking", "Clarity", "Application", "Understanding", "Creativity"]
        
        for criterion in criteria:
            # Use regex to find remarks and score for each criterion
            match = re.search(rf"{criterion}:\s*(.*?)\s*Score:\s*(\d+)", evaluation_content, re.DOTALL)
            if match:
                remarks = match.group(1).strip()
                score = int(match.group(2).strip())
                evaluation_data[criterion] = {"remarks": remarks, "score": score}

        # Extract overall remarks and suggestions for improvement
        overall_remarks_match = re.search(r"Overall Impression:\s*(.*?)\s*Suggestions for Improvement:\s*(.*)", evaluation_content, re.DOTALL)
        if overall_remarks_match:
            overall_remarks = overall_remarks_match.group(1).strip()
            suggestions = overall_remarks_match.group(2).strip()
            
            # Limit overall remarks to 4 sentences
            overall_remarks_sentences = re.split(r'(?<=[.!?]) +', overall_remarks)
            limited_remarks = ' '.join(overall_remarks_sentences[:4])  # Join only the first 4 sentences
            
            # Remove "Overall Score" sentence if present
            limited_remarks = re.sub(r"Overall Score:.*", "", limited_remarks).strip()
            
            # Convert suggestions into an ordered list format
            suggestions_list = re.split(r'\d+\.\s*', suggestions)[1:]  # Split on numbered points and ignore the first empty element
            suggestions_html = "<ol>" + "".join(f"<li>{item.strip()}</li>" for item in suggestions_list) + "</ol>"
            
            # Combine overall remarks with the suggestions list
            evaluation_data["Overall Remarks"] = f"{limited_remarks}<br>To improve: {suggestions_html}"
        
        # Calculate the total score
        total_score = sum(details["score"] for details in evaluation_data.values() if isinstance(details, dict) and "score" in details)
        evaluation_data["Total Score"] = total_score

        # Generate HTML table
        table_html = """
            <table class="w-full text-left border border-collapse border-gray-700">
                <tr>
                    <th class="p-2 border border-gray-600">Criteria</th>
                    <th class="p-2 border border-gray-600">Remarks</th>
                    <th class="p-2 border border-gray-600">Score</th>
                </tr>
        """

        for criterion, details in evaluation_data.items():
            if criterion in ["Total Score", "Overall Remarks"]:
                continue
            table_html += f"""
                <tr>
                    <td class="p-2 border border-gray-600">{criterion}</td>
                    <td class="p-2 border border-gray-600">{details['remarks']}</td>
                    <td class="p-2 border border-gray-600">{details['score']}</td>
                </tr>
            """

        # Add the total score and overall remarks with improvement suggestions
        table_html += f"""
                <tr>
                    <td class="p-2 border border-gray-600 font-bold">Total Score</td>
                    <td class="p-2 border border-gray-600 font-bold">{evaluation_data['Overall Remarks']}</td>
                    <td class="p-2 border border-gray-600 font-bold">{evaluation_data['Total Score']}</td>
                </tr>
            </table>
        """

        emit('evaluation', {'text': table_html})
    except Exception as e:
        print("Error generating evaluation:", e)
        traceback.print_exc()
        emit('evaluation', {'text': f'Error generating evaluation: {str(e)}'})

if __name__ == '__main__':
    socketio.run(app, debug=True, use_reloader=False)
