#!/usr/bin/env python3
"""
Parse Claude Code output from stream-json format.
Analyzes the last line of the JSON output file to check for errors.
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, Optional


def parse_claude_output(json_file_path: str) -> tuple[bool, Optional[Dict[str, Any]]]:
    """
    Parse the Claude Code stream-json output file.
    
    Args:
        json_file_path: Path to the JSON output file
        
    Returns:
        A tuple of (has_error, last_json_object)
    """
    try:
        file_path = Path(json_file_path)
        if not file_path.exists():
            print(f"Error: File {json_file_path} does not exist")
            return True, None
            
        # Read all lines from the file
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        if not lines:
            print("Error: Output file is empty")
            return True, None
            
        # Parse all JSON objects to check for errors
        has_error = False
        error_messages = []
        last_json = None
        
        for line in lines:
            line = line.strip()
            if line:
                try:
                    json_obj = json.loads(line)
                    last_json = json_obj
                    
                    # Check for error indicators in the JSON
                    if json_obj.get('type') == 'error':
                        has_error = True
                        error_messages.append(f"Error event: {json_obj.get('message', 'Unknown error')}")
                        
                    # Check for error in content field
                    if 'error' in str(json_obj.get('content', '')).lower():
                        has_error = True
                        error_messages.append(f"Error in content: {json_obj.get('content', '')[:200]}")
                        
                    # Check for failed tool calls
                    if json_obj.get('type') == 'tool_result' and not json_obj.get('success', True):
                        has_error = True
                        error_messages.append(f"Tool failed: {json_obj.get('tool_name', 'unknown')}")
                        
                except json.JSONDecodeError:
                    continue
                    
        if last_json is None:
            print("Error: No valid JSON found in output file")
            return True, None
            
        print(f"Last JSON object type: {last_json.get('type', 'unknown')}")
        
        # Check if the last event indicates success
        if last_json.get('type') == 'result':
            if last_json.get('status') == 'error':
                has_error = True
                error_messages.append(f"Final result status: error")
                
        if error_messages:
            print("Errors detected in Claude output:")
            for msg in error_messages:
                print(f"  - {msg}")
                
        if has_error:
            print("Claude execution contains errors")
        else:
            print("No errors detected in Claude output")
            
        return has_error, last_json
        
    except Exception as e:
        print(f"Error parsing Claude output: {e}")
        return False, None


def main():
    """Main entry point for the parser script."""
    if len(sys.argv) != 2:
        print("Usage: python parse_claude_code_result.py <json_output_file>")
        sys.exit(1)
        
    json_file = sys.argv[1]
    print(f"Parsing Claude output from: {json_file}")
    
    has_error, last_json = parse_claude_output(json_file)
    
    if has_error:
        print("ERROR: Claude execution failed or contains errors")
        sys.exit(1)
        
    # Exit with success code
    print("SUCCESS: Claude output parsed successfully without errors")
    sys.exit(0)


if __name__ == "__main__":
    main()