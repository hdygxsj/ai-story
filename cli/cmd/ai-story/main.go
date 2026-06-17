package main

import (
	"context"
	"os"

	"aistorycli/internal/command"
	"aistorycli/internal/config"
)

func main() {
	args := os.Args[1:]
	configPath, err := config.DefaultPath()
	if err != nil {
		configPath = ""
	}
	env := &command.Env{
		Stdout:     os.Stdout,
		Stderr:     os.Stderr,
		ConfigPath: configPath,
	}
	var commandArgs []string
	for i := 0; i < len(args); i++ {
		switch args[i] {
		case "--base-url":
			if i+1 >= len(args) {
				os.Exit(2)
			}
			env.BaseURL = args[i+1]
			i++
		case "--config":
			if i+1 >= len(args) {
				os.Exit(2)
			}
			env.ConfigPath = args[i+1]
			i++
		case "--json":
			env.JSON = true
		default:
			commandArgs = append(commandArgs, args[i:]...)
			i = len(args)
		}
	}
	if env.ConfigPath != "" {
		cfg, err := config.Load(env.ConfigPath)
		if err != nil {
			os.Exit(1)
		}
		env.Config = cfg
	}
	os.Exit(command.Execute(context.Background(), env, commandArgs))
}
