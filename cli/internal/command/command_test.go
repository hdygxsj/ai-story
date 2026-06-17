package command_test

import (
	"bytes"
	"context"
	"io"
	"strings"
	"testing"

	"aistorycli/internal/command"
)

func TestHelpIncludesTopLevelCommands(t *testing.T) {
	root := command.NewRoot(nil)
	got := root.Help()
	for _, want := range []string{"auth", "api", "tools", "agent", "config"} {
		if !strings.Contains(got, want) {
			t.Fatalf("help missing %q:\n%s", want, got)
		}
	}
}

func TestExecuteNestedHelpUsesNestedCommand(t *testing.T) {
	var stdout bytes.Buffer
	env := &command.Env{Stdout: &stdout, Stderr: io.Discard}
	code := command.Execute(context.Background(), env, []string{"tools", "run", "--help"})
	if code != 0 {
		t.Fatalf("exit code = %d", code)
	}
	got := stdout.String()
	for _, want := range []string{"Usage: ai-story tools run", "--json-arg", "--yes"} {
		if !strings.Contains(got, want) {
			t.Fatalf("nested help missing %q:\n%s", want, got)
		}
	}
}

func TestNestedHelpIncludesUsage(t *testing.T) {
	root := command.NewRoot(nil)
	cmd, ok := root.Find([]string{"tools", "run"})
	if !ok {
		t.Fatal("tools run command not found")
	}
	got := cmd.Help()
	for _, want := range []string{"Usage:", "--arg", "--json-arg", "--yes"} {
		if !strings.Contains(got, want) {
			t.Fatalf("tools run help missing %q:\n%s", want, got)
		}
	}
}
