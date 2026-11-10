import ast
import importlib.util
import re
from pathlib import Path

PLUGINS_DIR = Path(__file__).parent / "plugins"
PLUGINS_DIR.mkdir(exist_ok=True)

# Modules generated plugins may not import
BLOCKED_IMPORTS = {"os", "sys", "subprocess", "shutil", "socket", "ctypes", "importlib", "builtins"}
BLOCKED_CALLS = {"eval", "exec", "compile", "open", "__import__"}

PLUGINS = {}   # plugin name -> callable
AGENTS = {}    # agent name -> Agent
return_to = None  # agent that handed off to the plugin manager


def register_plugin(func):
    """Register a callable as a plugin. Also usable as a decorator."""
    PLUGINS[func.__name__] = func
    return func


def register_agent(agent):
    AGENTS[agent.name] = agent
    return agent


def _find_agent(agent_name):
    key = agent_name.strip().lower()
    for name, agent in AGENTS.items():
        if name.lower() == key:
            return agent
    return None


def load_plugin_files():
    """Import every plugins/*.py file and register its public functions."""
    loaded = []
    for path in sorted(PLUGINS_DIR.glob("*.py")):
        if path.name.startswith("_"):
            continue
        spec = importlib.util.spec_from_file_location(f"plugins.{path.stem}", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        func = getattr(module, path.stem, None)
        if callable(func):
            register_plugin(func)
            loaded.append(path.stem)
    return loaded


def _validate(code, name):
    tree = ast.parse(code)
    defines_entry = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods = [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            mods = [(node.module or "").split(".")[0]]
        else:
            mods = []
        for mod in mods:
            if mod in BLOCKED_IMPORTS:
                raise ValueError(f"Import of '{mod}' is not allowed in plugins.")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in BLOCKED_CALLS:
            raise ValueError(f"Call to '{node.func.id}' is not allowed in plugins.")
        if isinstance(node, ast.FunctionDef) and node.name == name and node in tree.body:
            defines_entry = True
    if not defines_entry:
        raise ValueError(f"Code must define a top-level function named '{name}'.")


# ---- Functions exposed to the floating plugin-manager agent ----

def list_plugins():
    """List all registered plugins and which agents currently use them."""
    lines = []
    for name, func in PLUGINS.items():
        users = [a.name for a in AGENTS.values() if func in a.functions]
        doc = (func.__doc__ or "").strip().split("\n")[0]
        lines.append(f"{name}: {doc} | used by: {', '.join(users) or 'nobody'}")
    return "\n".join(lines) or "No plugins registered."


def arrange_plugin(plugin_name, agent_name, action="add"):
    """Add or remove a plugin on an agent. action is 'add' or 'remove'.
    Takes as input arguments in the format '{"plugin_name":"order_item","agent_name":"Sales Agent","action":"add"}'"""
    func = PLUGINS.get(plugin_name)
    agent = _find_agent(agent_name)
    if func is None:
        return f"Unknown plugin '{plugin_name}'."
    if agent is None:
        return f"Unknown agent '{agent_name}'. Known agents: {', '.join(AGENTS)}."
    if action == "add":
        if func not in agent.functions:
            agent.functions.append(func)
        return f"Plugin '{plugin_name}' added to {agent.name}."
    if action == "remove":
        if func in agent.functions:
            agent.functions.remove(func)
        return f"Plugin '{plugin_name}' removed from {agent.name}."
    return "action must be 'add' or 'remove'."


def write_plugin(name, code, agent_name=""):
    """Write a new plugin to plugins/<name>.py, load it, and optionally attach it to an agent.
    The code must define a top-level function with the same name as the plugin, with a docstring.
    Takes as input arguments in the format '{"name":"get_weather","code":"def get_weather(city): ...","agent_name":"Product Agent"}'"""
    if not re.fullmatch(r"[a-z_][a-z0-9_]{0,40}", name) or name.startswith("_"):
        return "Invalid plugin name; use lowercase letters, digits and underscores."
    try:
        _validate(code, name)
    except (SyntaxError, ValueError) as e:
        return f"Plugin rejected: {e}"
    (PLUGINS_DIR / f"{name}.py").write_text(code, encoding="utf-8")
    load_plugin_files()
    message = f"Plugin '{name}' written and registered."
    if agent_name:
        message += " " + arrange_plugin(name, agent_name)
    return message


def make_transfer_to_plugin_manager(caller, manager):
    """Build a handoff function so any agent can reach the floating manager."""
    def transfer_to_plugin_manager():
        """Transfer to the Plugin Manager to list, arrange or write plugins."""
        global return_to
        return_to = caller
        return manager
    return transfer_to_plugin_manager


def make_transfer_back(default_agent):
    def transfer_back():
        """Return to the agent that requested plugin management."""
        return return_to or default_agent
    return transfer_back
