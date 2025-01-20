import json
import logging


def handle_save_config(mod_name, json_config):
    try:
        with open("Config/mod_config.json", "r") as f:
            data = json.load(f)
        data[mod_name] = json_config
        with open("Config/mod_config.json", "w") as json_file:
            json.dump(data, json_file, indent=4)
    except FileNotFoundError:
        data = {mod_name: json_config}
        print(json.dumps(data))
        with open("mod_config.json", "w") as json_file:
            json.dump(data, json_file, indent=4)
    except Exception as e:
        print(f"Failed to write config. {e}")


def handle_load_config(mod_name):
    try:
        with open("mod_config.json", "r") as f:
            data = json.load(f)
        result_data = data[mod_name]
        return data
    except FileNotFoundError as e:
        return f'mod_config.json not found.. Have you created a config save yet?'
    except Exception as e:
        logging.error(f'Unhandled Exception: {e}')
        return f'Unhandled Exception Occurred.'



