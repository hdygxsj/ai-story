package output

import (
	"encoding/json"
	"fmt"
	"io"
)

func JSON(w io.Writer, value any) error {
	data, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		return err
	}
	_, err = fmt.Fprintln(w, string(data))
	return err
}

func Bytes(w io.Writer, data []byte) error {
	_, err := w.Write(data)
	if len(data) > 0 && data[len(data)-1] != '\n' {
		_, _ = fmt.Fprintln(w)
	}
	return err
}

func Text(w io.Writer, format string, args ...any) error {
	_, err := fmt.Fprintf(w, format, args...)
	return err
}
