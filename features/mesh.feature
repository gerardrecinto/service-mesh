Feature: Service mesh behaviour

  Scenario: A 90/10 canary sends a small share of traffic to v2
    Given the traffic spec "mesh/traffic.yaml" is applied
    When I send 200 requests to "web" from the mesh client
    Then between 3 and 20 percent of responses are "v2"

  Scenario: Changing weights through meshctl changes real traffic
    Given the traffic spec "mesh/traffic.yaml" is applied
    When I set the weights "v1=50 v2=50" with meshctl and apply
    And I send 200 requests to "web" from the mesh client
    Then between 35 and 65 percent of responses are "v2"

  Scenario: A weight set that does not add up to 100 is refused
    When I try to set the weights "v1=70 v2=70" with meshctl
    Then meshctl refuses with "add up to 140"

  Scenario: A pod outside the mesh cannot call a STRICT mTLS service
    Given the traffic spec "mesh/traffic.yaml" is applied
    When a pod without a sidecar calls "web.shop:5678"
    Then the call fails
    And a pod in the mesh can call "web:5678"

  Scenario: A failing replica is ejected by outlier detection
    Given the traffic spec "mesh/pay.yaml" is applied
    When I send 80 slow requests to "pay" from the mesh client
    Then fewer than 30 responses are errors
    And the last 20 responses are all successful

  Scenario: Scaling up for a load test and back down
    When I scale "web-v1" to 3 replicas
    Then 3 replicas of "web-v1" are ready within 120 seconds
    And 300 requests to "web" return no errors
    When I scale "web-v1" to 1 replicas
    Then 1 replicas of "web-v1" are ready within 120 seconds
