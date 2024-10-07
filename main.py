import streamlit as st
from freshdesk.api import API
from bs4 import BeautifulSoup
import google.generativeai as genai
import traceback
import json
import os

JSON_FILE_PATH = 'api_keys.json'

class FreshDesk:
    def __init__(self, api_key):
        self.api_link = API('streetsheaver-help.freshdesk.com', api_key)
        genai.configure(api_key="AIzaSyDyNNcAG0tfeU5gZojE5zi7vimhy5QFQyE")
        self.model = genai.GenerativeModel("models/gemini-1.5-pro-latest")

    def ask_google_ai(self, comments_list):
        try:
            context = """Please supply a summary of this ticket contents below. 
                This needs to include: the original issue, the resolution, and any important information along the way.
                Write it in first person as the support agent. Use HTML tags for proper formatting.
                For the questions 'Is the time logged on the ticket accurate?' and 'Are the module and problem category accurate?' supply yes.
                Format it as follows with <br> tags for new lines:

                <br><strong>What was the Initial Problem?</strong><br>
                <br><strong>What was the Solution?</strong><br>
                <br><strong>Were there any knowledge base articles that you found helpful (please link below)?</strong><br>
                <br><strong>Are the module and problem category accurate?</strong><br>
                <br><strong>Is the time logged on the ticket accurate?</strong><br>
                """

            prompt = f"{context} {' '.join(comments_list)}"
            response = self.model.generate_content(prompt)
            return response.text.replace('\n', '<br>')
        except Exception as e:
            return f"Error occurred while processing the request: {e}"

    def get_ticket_comments(self, ticket_id):
        try:
            comments = self.api_link.comments.list_comments(ticket_id)
            all_comments = [BeautifulSoup(comment.__dict__["body"], "html.parser").get_text() for comment in comments]
            return all_comments
        except Exception:
            print(traceback.format_exc())
            return []

    def add_note_to_ticket(self, ticket_id, note):
        try:
            self.api_link.comments.create_note(ticket_id, note, private=True)
            return "Note added successfully!"
        except Exception as e:
            return f"Error adding note: {e}"

    def test_api_key(self):
        """Method to test the API key by making a simple request."""
        try:
            self.api_link.tickets.list_tickets()
            return True
        except Exception as e:
            print(f"API Key verification failed: {e}")
            return False

def read_api_keys():
    """Read the API keys from the JSON file."""
    if os.path.exists(JSON_FILE_PATH):
        with open(JSON_FILE_PATH, 'r') as file:
            return json.load(file)
    return {}

def write_api_keys(api_keys):
    """Write the API keys to the JSON file."""
    with open(JSON_FILE_PATH, 'w') as file:
        json.dump(api_keys, file)

def main():
    st.title("Freshdesk Ticket Summary Generator")

    api_keys = read_api_keys()

    if 'step' not in st.session_state:
        st.session_state.step = "email_input"

    if st.session_state.step == "email_input":
        email = st.text_input("Enter your email address:", key="email_input_field")  # Unique key
        if st.button("Next", key="next_email_button"):
            if email:
                email_lower = email.lower()
                if email_lower in api_keys:
                    st.session_state.api_key = api_keys[email_lower]  # Load from JSON
                    st.session_state.email = email
                    st.session_state.step = "ticket_id"  # Move to the next step
                else:
                    st.session_state.email = email  # Store email in session state for later use
                    st.session_state.step = "api_key"  # Move to API key input step
            else:
                st.warning("Please enter your email address.")

    # Step 2: Input API key
    elif st.session_state.step == "api_key":
        api_key = st.text_input("Enter your Freshdesk API key:", type="password", key="api_key_input_field")  # Unique key
        if st.button("Submit API Key", key="submit_api_key_button"):
            if api_key:
                freshdesk = FreshDesk(api_key)
                if freshdesk.test_api_key():
                    st.session_state.api_key = api_key  # Store API key in session state
                    api_keys[st.session_state.email.lower()] = api_key  # Save to JSON
                    write_api_keys(api_keys)  # Write updated API keys to JSON
                    st.session_state.step = "ticket_id"  # Move to the next step
                else:
                    st.error("Invalid API key. Please try again.")
            else:
                st.warning("Please enter your Freshdesk API key.")

    # Step 3: Input ticket ID
    elif st.session_state.step == "ticket_id":
        ticket_id = st.number_input("Enter the ticket ID:", min_value=1, key="ticket_id_input")  # Unique key
        if st.button("Generate Summary", key="generate_summary_button"):
            if ticket_id:
                freshdesk = FreshDesk(st.session_state.api_key)
                comments = freshdesk.get_ticket_comments(ticket_id)

                if comments:
                    summary = freshdesk.ask_google_ai(comments)
                    st.session_state.summary = summary  # Store summary in session state
                    st.markdown(f"### Generated Summary:\n{summary}", unsafe_allow_html=True)
                else:
                    st.warning("No comments found for this ticket.")
            else:
                st.warning("Please enter a valid ticket ID.")

        # Button to add the summary as a note
        if 'summary' in st.session_state:  # Check if summary exists in session state
            if st.button("Add Summary as Note", key="add_summary_note_button"):
                freshdesk = FreshDesk(st.session_state.api_key)
                response = freshdesk.add_note_to_ticket(ticket_id, st.session_state.summary)
                st.success(response)  
                else:
                    st.warning("No comments found for this ticket.")
            else:
                st.warning("Please enter a valid ticket ID.")

if __name__ == "__main__":
    main()
