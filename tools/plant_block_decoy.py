import os
import json
import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"

def get_decoy_syntax(lang):
    if lang in ("html", "xml", "markdown"):
        return ("<!--\nGraph Decoy: this block comment contains a fake function call.\nphantom_decoy_call();\n-->\n", "comment")
    elif lang == "haskell":
        return ("{-\nGraph Decoy: this block comment contains a fake function call.\nphantom_decoy_call();\n-}\n", "comment")
    elif lang == "lua":
        return ("--[[\nGraph Decoy: this block comment contains a fake function call.\nphantom_decoy_call();\n]]\n", "comment")
    elif lang in ("python", "elixir", "ruby"):
        return ("\"\"\"\nGraph Decoy: this multi-line string contains a fake function call.\nphantom_decoy_call();\n\"\"\"\n", "string")
    elif lang in ("shell", "bash", "perl", "r", "yaml", "cobol", "fortran", "abap", "assembly", "agc_assembly", "bms", "hlasm", "jcl", "makefile"):
        marker = "*" if lang in ("cobol", "bms", "jcl") else ("!" if lang == "fortran" else (";" if lang in ("assembly", "hlasm") else "#"))
        if lang == "agc_assembly":
            marker = "#"
        if lang == "jcl":
            marker = "//*"
        return (f"{marker} Graph Decoy: this comment cluster contains a fake function call.\n{marker} phantom_decoy_call();\n", "comment")
    else:
        return ("/*\nGraph Decoy: this block comment contains a fake function call.\nphantom_decoy_call();\n*/\n", "comment")

def plant_decoy():
    for lang_dir in DATA_DIR.iterdir():
        if not lang_dir.is_dir() or lang_dir.name == "c":
            continue  # Already did C, or not a directory
        
        lang = lang_dir.name
        manifest_path = lang_dir / "expected_signals.json"
        if not manifest_path.exists():
            continue
            
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
            
        # Find main file
        main_files = [f for f in manifest.get("files", {}) if "main" in f or "entry" in f or "App" in f or "index" in f or "Makefile" in f or "Dockerfile" in f]
        if not main_files:
            main_files = list(manifest.get("files", {}).keys())
            
        if not main_files:
            continue
            
        main_file = main_files[0]
        main_path = lang_dir / main_file
        
        if not main_path.exists():
            continue
            
        # Check if decoy already exists in manifest
        decoys = manifest.get("decoys", [])
        if any("phantom_decoy_call" in d.get("line_hint", "") for d in decoys):
            continue
            
        decoy_text, surface = get_decoy_syntax(lang)
        
        # Inject into source code
        with open(main_path, "r") as f:
            code = f.read()
            
        if "phantom_decoy_call" in code:
            continue
            
        # Try to inject after "entry" or similar
        lines = code.split("\n")
        injected = False
        for i, line in enumerate(lines):
            if ("entry" in line.lower() or "main" in line.lower()) and ("(" in line or "{" in line or ":" in line):
                lines.insert(i + 1, decoy_text.strip("\n"))
                injected = True
                break
                
        if not injected:
            # Just put it at the very end of the file
            lines.append(decoy_text.strip("\n"))
            
        with open(main_path, "w") as f:
            f.write("\n".join(lines) + "\n")
            
        # Update manifest
        outcome_text = "Graph Block-Comment Decoy (Rule 5): Asserts that multi-line block comments are successfully stripped by the literal shielder before Information Flow Graph extraction. The phantom call contributes 0 to the `calls_out_to` topology."
        if surface == "string":
            outcome_text = "Graph Multi-line String Decoy (Rule 5 Exempt Fallback): Asserts that large literal blocks are successfully shielded from the Information Flow Graph extraction. The phantom call contributes 0 to the `calls_out_to` topology."
        elif lang in ("shell", "bash", "perl", "r", "yaml", "cobol", "fortran", "abap", "assembly", "agc_assembly", "bms", "hlasm", "jcl", "makefile"):
            outcome_text = "Graph Single-Comment Cluster Decoy (Rule 5 Exempt Fallback): Language lacks multi-line block comments, fell back to single-line cluster. Asserts the phantom call contributes 0 to the `calls_out_to` topology."
            
        decoys.append({
            "file": main_file,
            "line_hint": "phantom_decoy_call",
            "surface": surface,
            "signals": [],
            "outcome": outcome_text
        })
        manifest["decoys"] = decoys
        
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)
            f.write("\n")
            
    print("Done planting decoys.")

if __name__ == "__main__":
    plant_decoy()
