package command

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"sort"
	"strconv"
	"strings"

	"aistorycli/internal/client"
	"aistorycli/internal/config"
	"aistorycli/internal/coverage"
	"aistorycli/internal/output"
)

type Env struct {
	Stdout     io.Writer
	Stderr     io.Writer
	Config     config.Config
	ConfigPath string
	BaseURL    string
	JSON       bool
	HTTPClient *http.Client
}

type RunFunc func(ctx context.Context, env *Env, args []string) error

type Command struct {
	Name     string
	Summary  string
	Usage    string
	Options  []string
	Children []*Command
	Run      RunFunc
	parent   *Command
}

func (c *Command) Add(children ...*Command) *Command {
	for _, child := range children {
		child.parent = c
		c.Children = append(c.Children, child)
	}
	sort.Slice(c.Children, func(i, j int) bool {
		return c.Children[i].Name < c.Children[j].Name
	})
	return c
}

func (c *Command) Find(args []string) (*Command, bool) {
	current := c
	for _, arg := range args {
		if strings.HasPrefix(arg, "-") {
			break
		}
		var found *Command
		for _, child := range current.Children {
			if child.Name == arg {
				found = child
				break
			}
		}
		if found == nil {
			return current, false
		}
		current = found
	}
	return current, true
}

func (c *Command) Help() string {
	var b strings.Builder
	if c.Summary != "" {
		fmt.Fprintf(&b, "%s\n\n", c.Summary)
	}
	usage := c.Usage
	if usage == "" {
		usage = c.path()
	}
	fmt.Fprintf(&b, "Usage: %s\n", usage)
	if len(c.Options) > 0 {
		b.WriteString("\nOptions:\n")
		for _, option := range c.Options {
			fmt.Fprintf(&b, "  %s\n", option)
		}
	}
	if len(c.Children) > 0 {
		b.WriteString("\nCommands:\n")
		for _, child := range c.Children {
			fmt.Fprintf(&b, "  %-18s %s\n", child.Name, child.Summary)
		}
	}
	return strings.TrimRight(b.String(), "\n") + "\n"
}

func (c *Command) path() string {
	var parts []string
	for current := c; current != nil; current = current.parent {
		if current.Name != "" {
			parts = append([]string{current.Name}, parts...)
		}
	}
	if len(parts) == 0 {
		return "ai-story"
	}
	return strings.Join(parts, " ")
}

func NewRoot(env *Env) *Command {
	_ = env
	root := &Command{
		Name:    "ai-story",
		Summary: "AI Story command line client.",
		Usage:   "ai-story [--base-url URL] [--config PATH] [--json] COMMAND [ARGS...]",
		Options: []string{
			"--base-url URL    Override backend URL",
			"--config PATH     Override config file path",
			"--json            Emit machine-readable JSON where supported",
			"--help            Show help",
		},
	}

	auth := (&Command{Name: "auth", Summary: "Register, login, and inspect the current account."}).Add(
		&Command{Name: "login", Summary: "Login and save the access token.", Usage: "ai-story auth login --login NAME --password PASSWORD"},
		&Command{Name: "logout", Summary: "Clear the saved access token.", Usage: "ai-story auth logout"},
		&Command{Name: "me", Summary: "Show the authenticated user.", Usage: "ai-story auth me"},
		&Command{Name: "register", Summary: "Create a user account.", Usage: "ai-story auth register --email EMAIL --username USERNAME --password PASSWORD"},
	)

	api := (&Command{Name: "api", Summary: "Call backend HTTP APIs."}).Add(
		&Command{Name: "agent", Summary: "Agent message HTTP API commands."},
		&Command{Name: "auth", Summary: "Authentication HTTP API commands."},
		&Command{Name: "confirmations", Summary: "Confirmation HTTP API commands."},
		&Command{Name: "context-settings", Summary: "Context settings HTTP API commands."},
		&Command{Name: "conversations", Summary: "Conversation HTTP API commands."},
		&Command{Name: "documents", Summary: "Document HTTP API commands."},
		&Command{Name: "materials", Summary: "Material HTTP API commands."},
		&Command{Name: "memory", Summary: "Memory HTTP API commands."},
		&Command{Name: "model-profiles", Summary: "Model profile HTTP API commands."},
		&Command{Name: "novels", Summary: "Novel HTTP API commands."},
		&Command{Name: "rag", Summary: "RAG HTTP API commands."},
		&Command{Name: "request", Summary: "Send a raw HTTP request.", Usage: "ai-story api request METHOD PATH [--body-json JSON]"},
		&Command{Name: "routes", Summary: "List covered backend routes.", Usage: "ai-story api routes"},
		&Command{Name: "search", Summary: "Search HTTP API commands."},
		&Command{Name: "workspace", Summary: "Workspace node HTTP API commands."},
	)

	tools := (&Command{Name: "tools", Summary: "Discover and run Agent runtime tools."}).Add(
		&Command{Name: "list", Summary: "List Agent tools.", Usage: "ai-story tools list"},
		&Command{Name: "run", Summary: "Run an Agent tool.", Usage: "ai-story tools run NOVEL_ID TOOL [--arg key=value] [--json-arg key=JSON] [--document-id ID] [--yes]", Options: []string{
			"--arg key=value       Add a string, bool, or numeric argument",
			"--json-arg key=JSON   Add a JSON argument value",
			"--document-id ID      Provide current document scope",
			"--yes                 Skip destructive-action confirmation",
		}},
		&Command{Name: "schema", Summary: "Show one Agent tool schema.", Usage: "ai-story tools schema TOOL"},
	)

	agent := (&Command{Name: "agent", Summary: "Send Agent messages."}).Add(
		&Command{Name: "ask", Summary: "Send a non-streaming Agent message.", Usage: "ai-story agent ask NOVEL_ID MESSAGE"},
		&Command{Name: "stream", Summary: "Send a streaming Agent message.", Usage: "ai-story agent stream NOVEL_ID MESSAGE"},
	)

	config := (&Command{Name: "config", Summary: "Inspect or update CLI configuration."}).Add(
		&Command{Name: "show", Summary: "Show saved configuration.", Usage: "ai-story config show"},
		&Command{Name: "set-base-url", Summary: "Save the backend base URL.", Usage: "ai-story config set-base-url URL"},
	)

	return root.Add(auth, api, tools, agent, config)
}

func Execute(ctx context.Context, env *Env, args []string) int {
	if env == nil {
		env = &Env{}
	}
	if env.Stdout == nil {
		env.Stdout = io.Discard
	}
	if env.Stderr == nil {
		env.Stderr = io.Discard
	}
	root := NewRoot(env)
	if len(args) == 0 {
		_, _ = fmt.Fprint(env.Stdout, root.Help())
		return 0
	}
	if hasHelp(args) {
		helpArgs := withoutHelp(args)
		if len(helpArgs) == 0 {
			_, _ = fmt.Fprint(env.Stdout, root.Help())
			return 0
		}
		cmd, _ := root.Find(helpArgs)
		_, _ = fmt.Fprint(env.Stdout, cmd.Help())
		return 0
	}

	switch args[0] {
	case "api":
		return executeAPI(ctx, env, args[1:])
	case "tools":
		return executeTools(ctx, env, args[1:])
	case "auth":
		return executeAuth(ctx, env, args[1:])
	case "agent":
		return executeAgent(ctx, env, args[1:])
	case "config":
		return executeConfig(env, args[1:])
	default:
		cmd, ok := root.Find(args)
		if ok {
			_, _ = fmt.Fprint(env.Stdout, cmd.Help())
			return 0
		}
		_, _ = fmt.Fprintf(env.Stderr, "unknown command: %s\n", args[0])
		return 2
	}
}

func hasHelp(args []string) bool {
	for _, arg := range args {
		if arg == "--help" || arg == "-h" {
			return true
		}
	}
	return false
}

func withoutHelp(args []string) []string {
	filtered := make([]string, 0, len(args))
	for _, arg := range args {
		if arg == "--help" || arg == "-h" {
			continue
		}
		filtered = append(filtered, arg)
	}
	return filtered
}

func newClient(env *Env) *client.Client {
	c := client.New(env.Config.ResolveBaseURL(env.BaseURL), env.Config.Token)
	if env.HTTPClient != nil {
		c.HTTPClient = env.HTTPClient
	}
	return c
}

func executeAPI(ctx context.Context, env *Env, args []string) int {
	if len(args) == 0 || hasHelp(args) {
		cmd, _ := NewRoot(env).Find([]string{"api"})
		_, _ = fmt.Fprint(env.Stdout, cmd.Help())
		return 0
	}
	switch args[0] {
	case "routes":
		for _, route := range coverage.Routes {
			_, _ = fmt.Fprintf(env.Stdout, "%s %s\n", route.Method, route.Path)
		}
		return 0
	case "request":
		if len(args) < 3 {
			_, _ = fmt.Fprintln(env.Stderr, "usage: ai-story api request METHOD PATH [--body-json JSON]")
			return 2
		}
		method := strings.ToUpper(args[1])
		path := args[2]
		body, ok := parseBodyJSON(env, args[3:])
		if !ok {
			return 2
		}
		data, err := newClient(env).Request(ctx, method, path, body)
		if err != nil {
			_, _ = fmt.Fprintln(env.Stderr, err)
			return 1
		}
		_ = output.Bytes(env.Stdout, data)
		return 0
	default:
		cmd, ok := NewRoot(env).Find(append([]string{"api"}, args...))
		if ok {
			_, _ = fmt.Fprint(env.Stdout, cmd.Help())
			return 0
		}
		_, _ = fmt.Fprintf(env.Stderr, "unknown api command: %s\n", args[0])
		return 2
	}
}

func parseBodyJSON(env *Env, args []string) (any, bool) {
	var body any
	for i := 0; i < len(args); i++ {
		if args[i] != "--body-json" {
			_, _ = fmt.Fprintf(env.Stderr, "unknown option: %s\n", args[i])
			return nil, false
		}
		if i+1 >= len(args) {
			_, _ = fmt.Fprintln(env.Stderr, "--body-json requires a value")
			return nil, false
		}
		if err := json.Unmarshal([]byte(args[i+1]), &body); err != nil {
			_, _ = fmt.Fprintf(env.Stderr, "invalid JSON body: %v\n", err)
			return nil, false
		}
		i++
	}
	return body, true
}

func executeTools(ctx context.Context, env *Env, args []string) int {
	if len(args) == 0 || hasHelp(args) {
		cmd, _ := NewRoot(env).Find([]string{"tools"})
		_, _ = fmt.Fprint(env.Stdout, cmd.Help())
		return 0
	}
	switch args[0] {
	case "list":
		return requestAndPrint(ctx, env, http.MethodGet, "/agent-tools", nil)
	case "schema":
		if len(args) < 2 {
			_, _ = fmt.Fprintln(env.Stderr, "usage: ai-story tools schema TOOL")
			return 2
		}
		return requestAndPrint(ctx, env, http.MethodGet, "/agent-tools/"+args[1], nil)
	case "run":
		if hasHelp(args) {
			cmd, _ := NewRoot(env).Find([]string{"tools", "run"})
			_, _ = fmt.Fprint(env.Stdout, cmd.Help())
			return 0
		}
		if len(args) < 3 {
			_, _ = fmt.Fprintln(env.Stderr, "usage: ai-story tools run NOVEL_ID TOOL [--arg key=value]")
			return 2
		}
		body, ok := parseToolRun(env, args[3:])
		if !ok {
			return 2
		}
		path := fmt.Sprintf("/novels/%s/agent/tools/%s", args[1], args[2])
		return requestAndPrint(ctx, env, http.MethodPost, path, body)
	default:
		_, _ = fmt.Fprintf(env.Stderr, "unknown tools command: %s\n", args[0])
		return 2
	}
}

func parseToolRun(env *Env, args []string) (map[string]any, bool) {
	arguments := map[string]any{}
	body := map[string]any{"arguments": arguments}
	for i := 0; i < len(args); i++ {
		switch args[i] {
		case "--arg":
			if i+1 >= len(args) {
				_, _ = fmt.Fprintln(env.Stderr, "--arg requires key=value")
				return nil, false
			}
			key, value, ok := splitKeyValue(args[i+1])
			if !ok {
				_, _ = fmt.Fprintf(env.Stderr, "invalid --arg: %s\n", args[i+1])
				return nil, false
			}
			arguments[key] = parseScalar(value)
			i++
		case "--json-arg":
			if i+1 >= len(args) {
				_, _ = fmt.Fprintln(env.Stderr, "--json-arg requires key=JSON")
				return nil, false
			}
			key, value, ok := splitKeyValue(args[i+1])
			if !ok {
				_, _ = fmt.Fprintf(env.Stderr, "invalid --json-arg: %s\n", args[i+1])
				return nil, false
			}
			var parsed any
			if err := json.Unmarshal([]byte(value), &parsed); err != nil {
				_, _ = fmt.Fprintf(env.Stderr, "invalid JSON argument %s: %v\n", key, err)
				return nil, false
			}
			arguments[key] = parsed
			i++
		case "--document-id":
			if i+1 >= len(args) {
				_, _ = fmt.Fprintln(env.Stderr, "--document-id requires a value")
				return nil, false
			}
			body["document_id"] = args[i+1]
			i++
		case "--yes":
		default:
			_, _ = fmt.Fprintf(env.Stderr, "unknown option: %s\n", args[i])
			return nil, false
		}
	}
	return body, true
}

func splitKeyValue(value string) (string, string, bool) {
	key, raw, ok := strings.Cut(value, "=")
	return key, raw, ok && key != ""
}

func parseScalar(value string) any {
	if value == "true" {
		return true
	}
	if value == "false" {
		return false
	}
	if integer, err := strconv.ParseInt(value, 10, 64); err == nil {
		return integer
	}
	if float, err := strconv.ParseFloat(value, 64); err == nil {
		return float
	}
	return value
}

func executeAuth(ctx context.Context, env *Env, args []string) int {
	if len(args) == 0 || hasHelp(args) {
		cmd, _ := NewRoot(env).Find([]string{"auth"})
		_, _ = fmt.Fprint(env.Stdout, cmd.Help())
		return 0
	}
	switch args[0] {
	case "me":
		return requestAndPrint(ctx, env, http.MethodGet, "/auth/me", nil)
	case "register":
		body, ok := parseFlagBody(env, args[1:], map[string]string{"--email": "email", "--username": "username", "--password": "password"})
		if !ok {
			return 2
		}
		return requestAndPrint(ctx, env, http.MethodPost, "/auth/register", body)
	case "login":
		body, ok := parseFlagBody(env, args[1:], map[string]string{"--login": "login", "--password": "password"})
		if !ok {
			return 2
		}
		data, err := newClient(env).Request(ctx, http.MethodPost, "/auth/login", body)
		if err != nil {
			_, _ = fmt.Fprintln(env.Stderr, err)
			return 1
		}
		var payload struct {
			AccessToken string `json:"access_token"`
		}
		if err := json.Unmarshal(data, &payload); err == nil && payload.AccessToken != "" {
			env.Config.Token = payload.AccessToken
			if env.ConfigPath != "" {
				if err := config.Save(env.ConfigPath, env.Config); err != nil {
					_, _ = fmt.Fprintf(env.Stderr, "failed to save token: %v\n", err)
					return 1
				}
			}
		}
		_ = output.Bytes(env.Stdout, data)
		return 0
	case "logout":
		env.Config.Token = ""
		if env.ConfigPath != "" {
			if err := config.Save(env.ConfigPath, env.Config); err != nil {
				_, _ = fmt.Fprintf(env.Stderr, "failed to save config: %v\n", err)
				return 1
			}
		}
		_, _ = fmt.Fprintln(env.Stdout, "Logged out.")
		return 0
	default:
		_, _ = fmt.Fprintf(env.Stderr, "unknown auth command: %s\n", args[0])
		return 2
	}
}

func executeAgent(ctx context.Context, env *Env, args []string) int {
	if len(args) == 0 || hasHelp(args) {
		cmd, _ := NewRoot(env).Find([]string{"agent"})
		_, _ = fmt.Fprint(env.Stdout, cmd.Help())
		return 0
	}
	if len(args) < 3 || (args[0] != "ask" && args[0] != "stream") {
		_, _ = fmt.Fprintln(env.Stderr, "usage: ai-story agent ask|stream NOVEL_ID MESSAGE")
		return 2
	}
	path := fmt.Sprintf("/novels/%s/agent/messages", args[1])
	if args[0] == "stream" {
		path += "/stream"
	}
	body := map[string]any{"message": strings.Join(args[2:], " ")}
	return requestAndPrint(ctx, env, http.MethodPost, path, body)
}

func executeConfig(env *Env, args []string) int {
	if len(args) == 0 || hasHelp(args) {
		cmd, _ := NewRoot(env).Find([]string{"config"})
		_, _ = fmt.Fprint(env.Stdout, cmd.Help())
		return 0
	}
	switch args[0] {
	case "show":
		_ = output.JSON(env.Stdout, env.Config)
		return 0
	case "set-base-url":
		if len(args) < 2 {
			_, _ = fmt.Fprintln(env.Stderr, "usage: ai-story config set-base-url URL")
			return 2
		}
		env.Config.BaseURL = args[1]
		if env.ConfigPath != "" {
			if err := config.Save(env.ConfigPath, env.Config); err != nil {
				_, _ = fmt.Fprintf(env.Stderr, "failed to save config: %v\n", err)
				return 1
			}
		}
		_ = output.JSON(env.Stdout, env.Config)
		return 0
	default:
		_, _ = fmt.Fprintf(env.Stderr, "unknown config command: %s\n", args[0])
		return 2
	}
}

func parseFlagBody(env *Env, args []string, fields map[string]string) (map[string]any, bool) {
	body := map[string]any{}
	for i := 0; i < len(args); i++ {
		field, ok := fields[args[i]]
		if !ok {
			_, _ = fmt.Fprintf(env.Stderr, "unknown option: %s\n", args[i])
			return nil, false
		}
		if i+1 >= len(args) {
			_, _ = fmt.Fprintf(env.Stderr, "%s requires a value\n", args[i])
			return nil, false
		}
		body[field] = args[i+1]
		i++
	}
	return body, true
}

func requestAndPrint(ctx context.Context, env *Env, method string, path string, body any) int {
	data, err := newClient(env).Request(ctx, method, path, body)
	if err != nil {
		_, _ = fmt.Fprintln(env.Stderr, err)
		return 1
	}
	_ = output.Bytes(env.Stdout, data)
	return 0
}
