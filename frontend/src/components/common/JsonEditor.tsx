import { useRef } from 'react';
import Editor, { OnMount } from '@monaco-editor/react';
import { Box, CircularProgress } from '@mui/material';
import type { editor } from 'monaco-editor';

interface JsonEditorProps {
  value: string;
  onChange: (value: string) => void;
  height?: string;
  readOnly?: boolean;
  language?: 'json' | 'plaintext';
}

export default function JsonEditor({
  value,
  onChange,
  height = '600px',
  readOnly = false,
  language = 'json',
}: JsonEditorProps) {
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);

  const handleEditorDidMount: OnMount = (editor, monaco) => {
    editorRef.current = editor;

    // Configure Monaco editor options
    editor.updateOptions({
      fontSize: 14,
      minimap: {
        enabled: true,
      },
      scrollBeyondLastLine: false,
      automaticLayout: true,
      formatOnPaste: true,
      formatOnType: true,
      wordWrap: 'on',
      lineNumbers: 'on',
      renderWhitespace: 'selection',
      bracketPairColorization: {
        enabled: true,
      },
      suggest: {
        showSnippets: true,
      },
      quickSuggestions: {
        other: true,
        comments: false,
        strings: true,
      },
    });

    // Register custom commands for formatting
    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => {
      // Format document on Ctrl/Cmd+S
      editor.getAction('editor.action.formatDocument')?.run();
    });

    // Register Ctrl+F for find (already built-in but ensures it works)
    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyF, () => {
      editor.getAction('actions.find')?.run();
    });

    // Register Ctrl+H for find and replace (already built-in)
    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyH, () => {
      editor.getAction('editor.action.startFindReplaceAction')?.run();
    });

    // Auto-format JSON documents on mount if it's valid JSON
    if (language === 'json') {
      try {
        JSON.parse(value);
        setTimeout(() => {
          editor.getAction('editor.action.formatDocument')?.run();
        }, 100);
      } catch {
        // If not valid JSON, don't format
      }
    }
  };

  const handleEditorChange = (newValue: string | undefined) => {
    if (newValue !== undefined) {
      onChange(newValue);
    }
  };

  return (
    <Box
      sx={{
        border: 1,
        borderColor: 'divider',
        borderRadius: 1,
        overflow: 'hidden',
        height,
      }}
    >
      <Editor
        height={height}
        defaultLanguage={language}
        value={value}
        onChange={handleEditorChange}
        onMount={handleEditorDidMount}
        theme="vs-dark"
        loading={
          <Box
            sx={{
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              height: '100%',
            }}
          >
            <CircularProgress />
          </Box>
        }
        options={{
          readOnly,
          selectOnLineNumbers: true,
          roundedSelection: false,
          cursorStyle: 'line',
          automaticLayout: true,
          glyphMargin: false,
          folding: true,
        }}
      />
    </Box>
  );
}
