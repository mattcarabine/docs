package common

import (
	"encoding/json"
	"fmt"
	"io"
	"io/ioutil"
	"regexp"
	"strings"

	"gopkg.in/yaml.v3"
)

type ExampleType string
type RenderType string

const (
	JS   ExampleType = "js"
	AQL  ExampleType = "aql"
	HTTP ExampleType = "http"

	INPUT        RenderType = "input"
	OUTPUT       RenderType = "output"
	INPUT_OUTPUT RenderType = "input/output"
)

// @Example represents an example request to be supplied to an arango instance
type Example struct {
	Type    ExampleType    `json:"type"`
	Options ExampleOptions `json:"options"` // The codeblock yaml part
	Code    string         `json:"code"`
}

// The yaml part in the codeblock
type ExampleOptions struct {
	Release  string                 `yaml:"release" json:"release"`                     // Arango instance to be used: nightly, release ...
	Name     string                 `yaml:"name" json:"name"`                           // Example Name
	Run      bool                   `yaml:"run,omitempty" json:"run,omitempty"`         // Choose if the example has to be run or not
	Version  string                 `yaml:"version" json:"version"`                     // Arango instance version to launch the example against
	Render   RenderType             `yaml:"render" json:"render"`                       // Return the example code, the example output or both
	Explain  bool                   `yaml:"explain,omitempty" json:"explain,omitempty"` // AQL @EXPLAIN flag
	BindVars map[string]interface{} `yaml:"bindVars,omitempty" json:"bindVars,omitempty"`
	Dataset  string                 `yaml:"dataset,omitempty" json:"dataset,omitempty"`
}

// Get an example code block, parse the yaml options and the code itself
func ParseExample(request io.Reader, exampleType ExampleType) (Example, error) {
	req, err := ioutil.ReadAll(request)
	if err != nil {
		Logger.Printf("Error reading Example body: %s\n", err.Error())
		return Example{}, err
	}

	// Parse the yaml part
	r, err := regexp.Compile("---[\\w\\s\\W]*---")
	if err != nil {
		return Example{}, fmt.Errorf("ParseExample error compiling regex: %s", err.Error())
	}

	options := r.Find(req)
	optionsYaml := ExampleOptions{}
	err = yaml.Unmarshal(options, &optionsYaml)
	if err != nil {
		return Example{}, fmt.Errorf("ParseExample error parsing options: %s", err.Error())
	}

	code := strings.Replace(string(req), string(options), "", -1)

	return Example{Type: exampleType, Options: optionsYaml, Code: code}, nil
}

func (r Example) String() string {
	j, err := json.Marshal(r)
	if err != nil {
		return ""
	}

	return string(j)
}

func (r ExampleOptions) String() string {
	j, err := json.Marshal(r)
	if err != nil {
		return ""
	}

	return string(j)
}

type ExampleResponse struct {
	Input   string         `json:"input"`
	Output  string         `json:"output"`
	Error   string         `json:"error"`
	Options ExampleOptions `json:"options"`
}

func (r ExampleResponse) String() string {
	j, err := json.Marshal(r)
	if err != nil {
		return ""
	}

	return string(j)
}
