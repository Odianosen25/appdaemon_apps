import adbase as ad

class ServicesApp(ad.ADBase):

    def initialize(self):
        self.adbase = self.get_ad_api()

        services = self.adbase.list_services() #retrieve all existing services
        data = {}

        for service in services:
            namespace = service["namespace"]
            domain = service["domain"]
            serv = service["service"]
            if namespace not in data:
                data[namespace] = []
            
            ad_service = f"{domain}/{serv}"

            if ad_service not in data[namespace]:
                data[namespace].append(ad_service)

        namespaces = list(data.keys()) # get the namespaces with services

        namespace_select = "input_select.service_namespace" #used to store the namespaces as a list
        service_select = "input_select.select_service" #used to store the services from the selected namespace from above. It changes dynamically 
        services_args = "input_text.service_args" #used to enter the args required
        service_boolean = "input_boolean.service_args" #used to instruct it to run the service
        self._results = "sensor.results"

        self.adbase.set_state(namespace_select, state="default", options=sorted(namespaces), friendly_name="Select Namespace") #create entity with namespace list
        self.adbase.set_state(services_args, state="", friendly_name="Service Args") #create entity with namespace list
        self.adbase.set_state(service_boolean, state="off", friendly_name="Service Run Input Boolen") #create input Boolen entity

        self.adbase.listen_event(self.service_registered, "service_registered", service_select=service_select, namespace_select=namespace_select, namespace="global") #listen to service registered across all namespaces
        self.adbase.listen_state(self.namespace_selected, namespace_select, service_select=service_select, immediate=True) #listen for when a namespace is selected
        self.adbase.listen_state(self.service_entered, service_boolean, new="on", service_select=service_select) #listen for when the user instructs to process
        self.adbase.listen_state(self.service_entered, services_args, service_select=service_select, immediate=True)

    def service_registered(self, event_name, data, kwargs): # a new service was registered
        self.adbase.log(f"{event_name}, {data}, {kwargs}", level="DEBUG")

        service_entity_id = kwargs["service_select"]
        namespace_entity_id = kwargs["namespace_select"]

        if "namespace" not in data:
            return

        namespace = data["namespace"]
        domain = data["domain"]
        service = data["service"]

        selected_namespace = self.adbase.get_state(namespace_entity_id)
        namespaces = self.adbase.get_state(namespace_entity_id, attribute="options")

        if namespace not in namespaces: # it hasn't been registered before
            namespaces.append(namespace)
            self.adbase.set_state(namespace_entity_id, state=selected_namespace, 
                options=sorted(namespaces)) # add it to the namespace list
            return

        elif namespace != selected_namespace:
            return

        ad_service = f"{domain}/{service}"

        options = self.adbase.get_state(service_entity_id, attribute="options", default=[])

        if ad_service not in options:
            options.append(ad_service)
            self.adbase.set_state(service_entity_id, options=sorted(options))

    def namespace_selected(self, entity, attribute, old, new, kwargs): # a new namespace was registered
        service_entity_id = kwargs["service_select"]
        serv_sensor = f"namespace.{new}_services"

        services = self.adbase.list_services(namespace=new) #retrieve all existing services
        data = []

        for service in services: #get the services for this namespace
            domain = service["domain"]
            serv = service["service"]
            
            ad_service = f"{domain}/{serv}"

            if ad_service not in data:
                data.append(ad_service)

        data = sorted(data)

        #now update the sensor to get the supported services
        self.adbase.set_state(service_entity_id, state=data[0], options=data, selected=new, friendly_name="Select Service")

    def service_entered(self, entity, attribute, old, new, kwargs):
        domain, device = self.adbase.split_entity(entity)

        if (new in [None, ""]) or (domain == "input_text" and "=" not in new):
            return

        if domain == "input_boolean":
            entity_id = f"input_text.{device}"
            state = self.adbase.get_state(entity_id, copy=False)
            
        else:
            state = new

        service_entity_id = kwargs["service_select"]

        comma_separated = []

        if state.strip() != "":
            comma_separated = state.split(",")

        service_data = {}

        for kw in comma_separated:
            kw = kw.strip()

            if "=" not in kw:
                self.adbase.error(f"The service args is not properly configured, as {kw}, has no '=' in it", level="ERROR")
                return

            key, arg = kw.split("=")

            key = key.strip()
            arg = arg.strip()

            if arg.find("|") != -1: # its a list
                arg = arg.split("|")

                value = []
                for i in arg:
                    if isinstance(i, str):
                        i = i.strip()
                    
                    try:
                        i = int(i)
                    
                    except:
                        pass

                    value.append(i)
            
            else:
                if arg.lower() in ["true", "false"]:
                    arg = eval(arg.title())
                
                value = arg

            service_data[key] = value

        namespace = self.adbase.get_state(service_entity_id, attribute="selected", copy=False)
        service_data["namespace"] = namespace
        service = self.adbase.get_state(service_entity_id, copy=False)
        
        #
        # run service call
        #

        res = self.adbase.call_service(service, **service_data)
        #self.adbase.set_state(self._results, state=res)

        if domain == "input_boolean":
            #reset the service run attribute, just in case
            self.adbase.set_state(entity, state="off")