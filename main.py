import streamlit as st
from freshdesk.api import API
from bs4 import BeautifulSoup
import google.generativeai as genai
import traceback
import json
import os
from datetime import datetime, timedelta

JSON_FILE_PATH = 'api_keys.json'
AGENTS_FILE_PATH = 'agents_data.json'

class FreshDesk:
    def __init__(self, api_key):
        self.api_link = API('streetsheaver-help.freshdesk.com', api_key)
        genai.configure(api_key="AIzaSyDyNNcAG0tfeU5gZojE5zi7vimhy5QFQyE")
        self.model = genai.GenerativeModel("models/gemini-1.5-pro-latest")
        self.agents = self.load_agents()

    def load_agents(self):
        if os.path.exists(AGENTS_FILE_PATH):
            try:
                with open(AGENTS_FILE_PATH, 'r') as file:
                    agents_data = json.load(file)
                    stored_date = agents_data.get('stored_date')
                    
                    if stored_date:
                        stored_date = datetime.strptime(stored_date, '%Y-%m-%d')
                        if datetime.now() - stored_date > timedelta(days=7):
                            return self.fetch_and_store_agents()
                    else:
                        return self.fetch_and_store_agents()
    
                    if 'agents' in agents_data:
                        return agents_data['agents']
                    else:
                        return self.fetch_and_store_agents()
    
            except (ValueError, KeyError, json.JSONDecodeError):
                return self.fetch_and_store_agents()
        else:
            return self.fetch_and_store_agents()


    def fetch_and_store_agents(self):
        try:
            agents = self.api_link.agents.list_agents()
            agent_emails = [agent.contact['email'] for agent in agents]
            agents_data = {
                'agents': agent_emails,
                'stored_date': datetime.now().strftime('%Y-%m-%d')
            }
            with open(AGENTS_FILE_PATH, 'w') as file:
                json.dump(agents_data, file)
            return agent_emails
        except Exception as e:
            print(f"Error fetching agents: {e}")
            return []

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
        try:
            self.api_link.tickets.list_tickets()
            return True
        except Exception as e:
            print(f"API Key verification failed: {e}")
            return False

def read_api_keys():
    if os.path.exists(JSON_FILE_PATH):
        with open(JSON_FILE_PATH, 'r') as file:
            return json.load(file)
    return {}

def write_api_keys(api_keys):
    with open(JSON_FILE_PATH, 'w') as file:
        json.dump(api_keys, file)

def main():
    st.title("Freshdesk Ticket Summary Generator")

    api_keys = read_api_keys()

    if 'step' not in st.session_state:
        st.session_state.step = "email_input"

    freshdesk = None

    if st.session_state.step == "email_input":
        email = st.text_input("Enter your email address:", key="email_input_field")  
        if st.button("Next", key="next_email_button"):
            if email:
                if "streets-heaver.com" not in email.lower():
                    return st.error("Please use your work email associated with your Freshdesk account.")

                email_lower = email.lower()

                if email_lower in api_keys:
                    st.session_state.api_key = api_keys[email_lower]
                    freshdesk = FreshDesk(st.session_state.api_key)
                    st.session_state.email = email
                    st.session_state.step = "ticket_id"
                else:
                    st.session_state.email = email
                    st.session_state.step = "api_key"
            else:
                st.warning("Please enter your email address.")

    elif st.session_state.step == "api_key":
        api_key = st.text_input("Enter your Freshdesk API key:", type="password", key="api_key_input_field")
        if st.button("Submit API Key", key="submit_api_key_button"):
            if api_key:
                freshdesk = FreshDesk(api_key)
                if freshdesk.test_api_key():
                    st.session_state.api_key = api_key
                    api_keys[st.session_state.email.lower()] = api_key
                    write_api_keys(api_keys)

                    if st.session_state.email.lower() in (agent.lower() for agent in freshdesk.agents):
                        st.session_state.step = "ticket_id"
                        st.success("API Key Verified.")
                    else:
                        st.error("Your email is not listed as an agent in Freshdesk.")
                else:
                    st.error("Invalid API key. Please try again.")
                    if st.session_state.email.lower() not in (agent.lower() for agent in freshdesk.agents):
                        st.error("Your email is not listed as an agent in Freshdesk.")
            else:
                st.warning("Please enter your Freshdesk API key.")

    elif st.session_state.step == "ticket_id":
        ticket_id = st.number_input("Enter the ticket ID:", min_value=1, key="ticket_id_input")
        if st.button("Generate Summary", key="generate_summary_button"):
            if ticket_id:
                freshdesk = FreshDesk(st.session_state.api_key)
                comments = freshdesk.get_ticket_comments(ticket_id)

                if comments:
                    summary = freshdesk.ask_google_ai(comments)
                    st.session_state.summary = summary
                    st.markdown(f"### Generated Summary:\n{summary}", unsafe_allow_html=True)
                else:
                    st.warning("No comments found for this ticket.")
            else:
                st.warning("Please enter a valid ticket ID.")

        if 'summary' in st.session_state:
            if st.button("Add Summary as Note", key="add_summary_note_button"):
                freshdesk = FreshDesk(st.session_state.api_key)
                response = freshdesk.add_note_to_ticket(ticket_id, st.session_state.summary)
                st.success(response)


if __name__ == "__main__":
    main()
