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

package grasp

import (
	"io"
	"log"
	"net"
	"net/http"
	"net/url"

	"github.com/elastic/geneve/cmd/geneve/sink"
)

var logger *log.Logger

func ReopenLogger(w io.Writer) {
	logger = log.New(w, "reflect ", log.LstdFlags|log.Lmsgprefix)
}

func StartReflector(addr, remote string, reflections chan<- *Reflection) error {
	log.Printf("Remote: %s", remote)
	log.Printf("Local: http://%s", addr)

	remote_url, _ := url.Parse(remote)
	client := &http.Client{}

	mux := http.NewServeMux()
	mux.HandleFunc("/", func(w http.ResponseWriter, req *http.Request) {
		refl := &Reflection{}

		ref_req, err := refl.ReflectRequest(req, remote_url)
		if err != nil {
			log.Printf("ReflectionRequest: %s", err.Error())
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}

		resp, err := client.Do(ref_req)
		if err != nil {
			log.Printf("ClientDo: %s", err.Error())
			http.Error(w, err.Error(), http.StatusBadGateway)
			return
		}
		defer resp.Body.Close()

		err = refl.ReflectResponse(resp, w)
		if err != nil {
			log.Printf("ReflectionResponse: %s", err.Error())
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}

		select {
		case reflections <- refl:
		default:
			logger.Println("Blocking on reflections channel...")
			reflections <- refl
			logger.Println("Unblocked from reflections channel")
		}
	})

	listener, err := net.Listen("tcp", addr)
	if err != nil {
		return err
	}

	sink.Put("reflector", &sink.Sink{Params: sink.Params{URL: remote}})

	go func() {
		log.Fatal(http.Serve(listener, mux))
	}()
	return nil
}

func init() {
	ReopenLogger(log.Writer())
}
