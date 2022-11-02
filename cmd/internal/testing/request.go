// Licensed to Elasticsearch B.V. under one or more contributor
// license agreements. See the NOTICE file distributed with
// this work for additional information regarding copyright
// ownership. Elasticsearch B.V. licenses this file to you under
// the Apache License, Version 2.0 (the "License"); you may
// not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
// 	http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing,
// software distributed under the License is distributed on an
// "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
// KIND, either express or implied.  See the License for the
// specific language governing permissions and limitations
// under the License.

package testing

import (
	"net/http"
	"strings"
)

var client = &http.Client{}

type Request struct {
	URL string
}

func (r Request) Get(endpoint string) Response {
	req, err := http.NewRequest("GET", r.URL+endpoint, nil)
	if err != nil {
		panic(err)
	}
	resp, err := client.Do(req)
	if err != nil {
		panic(err)
	}
	return Response{resp}
}

func (r Request) bodyRequest(method, endpoint, content_type, body string) Response {
	req, err := http.NewRequest(method, r.URL+endpoint, strings.NewReader(body))
	if err != nil {
		panic(err)
	}
	if content_type != "" {
		req.Header.Set("Content-Type", content_type)
	}
	resp, err := client.Do(req)
	if err != nil {
		panic(err)
	}
	return Response{resp}
}

func (r Request) Put(endpoint, content_type, body string) Response {
	return r.bodyRequest("PUT", endpoint, content_type, body)
}

func (r Request) Post(endpoint, content_type, body string) Response {
	return r.bodyRequest("POST", endpoint, content_type, body)
}

func (r Request) Delete(endpoint string) Response {
	req, err := http.NewRequest("DELETE", r.URL+endpoint, nil)
	if err != nil {
		panic(err)
	}
	resp, err := client.Do(req)
	if err != nil {
		panic(err)
	}
	return Response{resp}
}