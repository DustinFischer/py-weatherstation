### MQTT
... create user if not one exists
https://github.com/vvatelot/mosquitto-docker-compose/blob/main/README.md

### Sensor
1. Compile and run the sensor latest firmware from a .yaml file (see `example/`)
```
$ esphome run --device /dev/cu.usbserial-11420 /path/to/eshphome/config/file
```


### Mosquitto and Kafka

1. install and run dependedncies:
```
$ docker compose up -d deps
```

2. wait for Kafka Connect to be up and running:
```
$ curl localhost:8083/
```
3. verify MQTT Connector is installed
```
$ curl localhost:8083/connector-plugins
```

4. install connector
```
$ curl -XPOST -d @path/to/connector/config.conf "Content-Type: application/json" http://localhost:8083/connectors | jq '.'
```

#### HomeAssistant
Dashboard:
```
$ localhost:8123
```
