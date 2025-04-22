import os
import json
import shutil
import logging
import argparse
from pathlib import Path
import winreg
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

ROOT = winreg.HKEY_LOCAL_MACHINE
POLICY_PATH = r"Software\Policies\BraveSoftware\Brave"

def get_user_data_dir():
    home = Path(os.environ.get('USERPROFILE') or os.environ.get('HOME'))
    cand = home / 'AppData' / 'Local' / 'BraveSoftware' / 'Brave-Browser' / 'User Data'
    if cand.exists():
        return cand
    raise FileNotFoundError("Brave user data directory not found")

def read_registry_value(name):
    try:
        reg = winreg.OpenKey(ROOT, POLICY_PATH, 0, winreg.KEY_READ)
        val, typ = winreg.QueryValueEx(reg, name)
        winreg.CloseKey(reg)
        return val, typ
    except FileNotFoundError:
        return None, None

def read_registry_policies_all():
    out = {}
    try:
        reg = winreg.OpenKey(ROOT, POLICY_PATH, 0, winreg.KEY_READ)
    except FileNotFoundError:
        return out
    i = 0
    while True:
        try:
            name, val, typ = winreg.EnumValue(reg, i)
            t = 'REG_DWORD' if typ == winreg.REG_DWORD else 'REG_SZ'
            out[name] = {'value': val, 'type': t}
            i += 1
        except OSError:
            break
    winreg.CloseKey(reg)
    return out

def load_json(path):
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        logging.error(f"Failed to parse JSON at {path}")
        return {}

def filter_by_paths(data, paths):
    out = {}
    for p in paths:
        keys = p.split('.')
        cur = data
        ok = True
        for k in keys:
            if isinstance(cur, dict) and k in cur:
                cur = cur[k]
            else:
                ok = False
                break
        if ok:
            sub = out
            for k in keys[:-1]:
                sub = sub.setdefault(k, {})
            sub[keys[-1]] = cur
    return out

def export_selected(path: Path):
    default_path = Path('default.json')
    if not default_path.exists():
        logging.error("default.json not found")
        return

    with open(default_path, 'r', encoding='utf-8') as f:
        default_data = json.load(f)

    tmp_path = Path('_full_export_tmp.json')
    export_all(tmp_path)

    with open(tmp_path, 'r', encoding='utf-8') as f:
        full_data = json.load(f)
    tmp_path.unlink(missing_ok=True)

    def filter_subset(source, template):
        if not isinstance(source, dict) or not isinstance(template, dict):
            return source
        result = {}
        for key, tpl_value in template.items():
            if key in source:
                if isinstance(tpl_value, dict):
                    sub = filter_subset(source[key], tpl_value)
                    if sub:
                        result[key] = sub
                else:
                    result[key] = source[key]
        return result

    data = {
        'registry': filter_subset(full_data.get('registry', {}), default_data.get('registry', {})),
        'Default_Preferences': filter_subset(full_data.get('Default_Preferences', {}), default_data.get('Default_Preferences', {})),
        'Local_State': filter_subset(full_data.get('Local_State', {}), default_data.get('Local_State', {}))
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    logging.info(f"Export selected to {path}")

def export_all(path: Path):
    data = {
        'registry': read_registry_policies_all(),
        'Default_Preferences': load_json(get_user_data_dir() / 'Default' / 'Preferences'),
        'Local_State': load_json(get_user_data_dir() / 'Local State')
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    logging.info(f"Export all to {path}")

def set_reg_value(key, subkey, name, value, reg_type):
    reg = winreg.CreateKeyEx(key, subkey, 0, winreg.KEY_SET_VALUE)
    winreg.SetValueEx(reg, name, 0, reg_type, value)
    winreg.CloseKey(reg)
    logging.info(f"REG SET: {name} = {value}")

def apply_registry(registry_policies):
    for name, entry in registry_policies.items():

        val = entry['value']
        typ = winreg.REG_DWORD if entry['type']=='REG_DWORD' else winreg.REG_SZ
        set_reg_value(ROOT, POLICY_PATH, name, val, typ)
    logging.info("Registry applied")

def backup_file(path: Path):
    if path.exists():
        shutil.copy2(path, path.with_suffix(path.suffix + '.bak'))
        logging.info(f"Backed up {path}")

def save_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    logging.info(f"Wrote JSON to {path}")

def apply_json(configs: dict):
    ud = get_user_data_dir()
    ls = ud / 'Local State'
    pref = ud / 'Default' / 'Preferences'
    backup_file(ls)
    backup_file(pref)
    save_json(ls, configs.get('Local_State', {}))
    save_json(pref, configs.get('Default_Preferences', {}))
    logging.info("JSON configs applied")

def import_all(path: Path):
    data = load_json(path)
    apply_registry(data.get('registry', {}))
    apply_json(data)

    logging.info(f"Imported from {path}")

def main():
    p = argparse.ArgumentParser()
    p.add_argument('-export', dest='sel', metavar='file.json', type=Path)
    p.add_argument('-export-all', dest='all', metavar='file.json', type=Path)
    p.add_argument('-import', dest='imp', metavar='file.json', type=Path)
    args = p.parse_args()

    if args.sel:
        export_selected(args.sel)
    elif args.all:
        export_all(args.all)
    elif args.imp:
        import_all(args.imp)
    else:
        p.print_help()

if __name__ == '__main__':
    main()