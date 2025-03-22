from flask import Flask, request, jsonify
import os
import requests
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from pprint import pprint

app = Flask(__name__)

@app.route('/trello-webhook', methods=['HEAD', 'POST'])
def trello_webhook():
    if request.method == 'HEAD':
        return '', 200
    elif request.method == 'POST':
        data = request.json

        pprint(data)
        handle_trello_event(data)
        return jsonify({'status': 'success'}), 200
    

GROUP_TO_CHANNEL = {
    'Design': 'C08JTQ23GHK',     # Replace with your Slack channel ID for Design
    'Production': 'C08JTQA3LER', # Replace with your Slack channel ID for Production
    'Event': 'C08JYELLQAF',      # Replace with your Slack channel ID for Event
    'Marketing': 'C08JZUNA1FW',
    'Uncategorized': 'C08JZNGN7TN' # Default channel for uncategorized tasks
}

def get_card_group_value(card_id, group_field_id):
    url = f"https://api.trello.com/1/cards/{card_id}/customFieldItems"
    query = {
        'key': os.getenv('TRELLO_API_KEY'),
        'token': os.getenv('TRELLO_API_TOKEN')
    }
    try:
        response = requests.get(url, params=query)
        response.raise_for_status()
        custom_fields = response.json()
        for field in custom_fields:
            pprint(field)
            if field['idCustomField'] == group_field_id:
                # Check if the field has a 'value' field that's a dictionary with 'text'
                if field.get('value') and isinstance(field['value'], dict) and 'text' in field['value']:
                    return field['value']['text']
                # If 'value' is None but there's an 'idValue', fetch the option value
                elif field.get('idValue'):
                    return get_custom_field_option_value(group_field_id, field['idValue'])
        # If the 'group' custom field is not found
        return 'Uncategorized'
    except requests.exceptions.RequestException as e:
        print(f"Error fetching card custom fields: {e}")
        return 'Uncategorized'

def get_custom_field_option_value(custom_field_id, option_id):
    """Fetch the text value of a custom field option from Trello API"""
    url = f"https://api.trello.com/1/customFields/{custom_field_id}/options/{option_id}"
    query = {
        'key': os.getenv('TRELLO_API_KEY'),
        'token': os.getenv('TRELLO_API_TOKEN')
    }
    try:
        response = requests.get(url, params=query)
        response.raise_for_status()
        option_data = response.json()
        # Return the option value text or a default
        return option_data.get('value', {}).get('text', 'Uncategorized')
    except requests.exceptions.RequestException as e:
        print(f"Error fetching custom field option: {e}")
        return 'Uncategorized'

def handle_trello_event(data):
    action_type = data.get('action', {}).get('type', '')
    card = data.get('action', {}).get('data', {}).get('card', {})
    member_creator = data.get('action', {}).get('memberCreator', {}).get('fullName', 'Someone')
    board_id = data.get('action', {}).get('data', {}).get('board', {}).get('id', '')

    # Retrieve the 'group' custom field ID
    custom_fields = get_custom_fields(board_id)
    group_field_id = None
    if custom_fields:
        for field in custom_fields:
            if field['name'] == 'group':
                group_field_id = field['id']
                break

    # Retrieve the 'group' value for the card
    group_value = get_card_group_value(card.get('id'), group_field_id) if group_field_id else 'Uncategorized'
    channel_id = GROUP_TO_CHANNEL.get(group_value, GROUP_TO_CHANNEL['Uncategorized'])

    if action_type == 'updateCard':
        # Example: A card has been updated
        message = f"📝 *{member_creator}* updated the task \"{card.get('name')}\" in the \"{group_value}\" group."
        send_slack_notification(channel_id, message)
    elif action_type == 'addMemberToCard':
        # Example: A member has been added to a card
        member = data.get('action', {}).get('member', {}).get('fullName', 'A member')
        message = f"👤 *{member_creator}* assigned *{member}* to the task \"{card.get('name')}\" in the \"{group_value}\" group."
        send_slack_notification(channel_id, message)

def get_custom_fields(board_id):
    url = f"https://api.trello.com/1/boards/{board_id}/customFields"
    query = {
        'key': os.getenv('TRELLO_API_KEY'),
        'token': os.getenv('TRELLO_API_TOKEN')
    }
    try:
        response = requests.get(url, params=query)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching custom fields: {e}")
        return None

def get_checklist_items(checklist_id):
    # Trello API endpoint to fetch checklist items
    url = f"https://api.trello.com/1/checklists/{checklist_id}/checkItems"
    query = {
        'key': os.getenv('TRELLO_API_KEY'),
        'token': os.getenv('TRELLO_API_TOKEN')
    }
    try:
        response = requests.get(url, params=query)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching checklist items: {e}")
        return None
    

def send_slack_notification(channel_id, message):
    slack_token = os.getenv('SLACK_BOT_TOKEN')
    if slack_token:
        client = WebClient(token=slack_token)
        try:
            response = client.chat_postMessage(
                channel=channel_id,
                text=message
            )
            print(f"Message sent to channel {channel_id}: {response['message']['text']}")
        except SlackApiError as e:
            print(f"Error sending message to Slack: {e.response['error']}")
    else:
        print("Slack bot token not configured.")


if __name__ == '__main__':
    app.run(port=5000, debug=True)
