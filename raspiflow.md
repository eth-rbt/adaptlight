  ---                                                                                                                                             
  1. Entry Points: Button Press or Voice Command                                                                                                  
                                                                                                                                                  
  Button Press Flow                                                                                                                               
                                                                                                                                                  
  ButtonController (GPIO interrupt)                                                                                                               
      ↓                                                                                                                                           
  on_click / on_hold / on_double_click / on_release callback                                                                                      
      ↓                                                                                                                                           
  main.py: _handle_button(event)                                                                                                                  
      ↓                                                                                                                                           
  smgen.trigger(event)           # e.g., "button_click"                                                                                           
      ↓                                                                                                                                           
  state_machine.execute_transition(event)                                                                                                         
      ↓                                                                                                                                           
  main.py: _execute_state(state_dict)                                                                                                             
                                                                                                                                                  
  Voice Command Flow                                                                                                                              
                                                                                                                                                  
  Record button pressed → VoiceInput.start_recording()                                                                                            
      ↓                                                                                                                                           
  Record button pressed again → VoiceInput.stop_recording()                                                                                       
      ↓                                                                                                                                           
  Transcription (Replicate/Whisper/etc.)                                                                                                          
      ↓                                                                                                                                           
  main.py: smgen.process(transcribed_text)                                                                                                        
      ↓                                                                                                                                           
  AgentProcessor runs Claude with tools                                                                                                           
      ↓                                                                                                                                           
  Tools modify state_machine (createState, appendRules, setState, etc.)                                                                           
      ↓                                                                                                                                           
  Returns SMResult with new state                                                                                                                 
      ↓                                                                                                                                           
  main.py: _execute_state(result.state)                                                                                                           
                                                                                                                                                  
  ---                                                                                                                                             
  2. State Transition: execute_transition(action)                                                                                                 
                                                                                                                                                  
  Location: brain/core/state_machine.py:445                                                                                                       
                                                                                                                                                  
  def execute_transition(self, action: str) -> bool:                                                                                              
      # 1. Find all matching rules (current_state + action)                                                                                       
      candidate_rules = [r for r in self.rules if r.matches(self.current_state, action)]                                                          
                                                                                                                                                  
      # 2. Sort by priority (highest first)                                                                                                       
      candidate_rules.sort(key=lambda r: r.priority, reverse=True)                                                                                
                                                                                                                                                  
      # 3. Find first rule whose condition passes                                                                                                 
      for rule in candidate_rules:                                                                                                                
          if not rule.condition or self.evaluate_rule_expression(rule.condition):                                                                 
              matching_rule = rule                                                                                                                
              break                                                                                                                               
                                                                                                                                                  
      # 4. Execute action expression (if any)                                                                                                     
      if matching_rule.action:                                                                                                                    
          self.evaluate_rule_expression(matching_rule.action, 'action')                                                                           
                                                                                                                                                  
      # 5. Execute pipeline (if any)                                                                                                              
      if matching_rule.pipeline:                                                                                                                  
          self._execute_pipeline(matching_rule.pipeline)                                                                                          
                                                                                                                                                  
      # 6. Transition to new state                                                                                                                
      self.set_state(matching_rule.state2)                                                                                                        
                                                                                                                                                  
  ---                                                                                                                                             
  3. Setting State: set_state(state_name)                                                                                                         
                                                                                                                                                  
  Location: brain/core/state_machine.py:359                                                                                                       
                                                                                                                                                  
  def set_state(self, state_name: str, params=None):                                                                                              
      self.current_state = state_name                                                                                                             
      self.current_state_params = params                                                                                                          
      print(f"State changed to: {state_name}")                                                                                                    
                                                                                                                                                  
      # Call the state's enter() method                                                                                                           
      state_object = self.get_state_object(state_name)                                                                                            
      if state_object:                                                                                                                            
          state_object.enter(params)                                                                                                              
                                                                                                                                                  
  Note: state_object.enter() calls _on_enter_callback if set, but in the current code this callback is NOT connected to the LED output. The LED   
  update happens separately via _execute_state().                                                                                                 
                                                                                                                                                  
  ---                                                                                                                                             
  4. Executing State on LED: _execute_state(state_dict)                                                                                           
                                                                                                                                                  
  Location: apps/raspi/main.py:240                                                                                                                
                                                                                                                                                  
  def _execute_state(self, state: dict):                                                                                                          
      from .output.light_states import execute_unified_state                                                                                      
      execute_unified_state(state)  # Uses globals: led_controller, state_machine_ref                                                             
                                                                                                                                                  
  ---                                                                                                                                             
  5. LED Output: execute_unified_state(params)                                                                                                    
                                                                                                                                                  
  Location: apps/raspi/output/light_states.py:82                                                                                                  
                                                                                                                                                  
  def execute_unified_state(params):                                                                                                              
      # 1. Handle voice_reactive mode                                                                                                             
      if voice_reactive_config and voice_reactive_config.get('enabled'):                                                                          
          voice_reactive_controller.start()                                                                                                       
                                                                                                                                                  
      # 2. Check if static or animated                                                                                                            
      speed = params.get('speed')                                                                                                                 
                                                                                                                                                  
      if speed is None:                                                                                                                           
          _execute_static_state(params)                                                                                                           
      else:                                                                                                                                       
          _execute_animated_state(params)                                                                                                         
                                                                                                                                                  
      # 3. Set up duration timer if needed                                                                                                        
      if duration_ms and then_state:                                                                                                              
          _setup_duration_timer(duration_ms, then_state, state_name)                                                                              
                                                                                                                                                  
  ---                                                                                                                                             
  6. Static Color: _execute_static_state(params)                                                                                                  
                                                                                                                                                  
  Location: apps/raspi/output/light_states.py:152                                                                                                 
                                                                                                                                                  
  def _execute_static_state(params):                                                                                                              
      # Stop any running animation                                                                                                                
      state_machine_ref.stop_interval()                                                                                                           
                                                                                                                                                  
      # Get current color for expression context                                                                                                  
      current_r, current_g, current_b = led_controller.get_current_color()                                                                        
                                                                                                                                                  
      r = params.get('r', 0)                                                                                                                      
      g = params.get('g', 0)                                                                                                                      
      b = params.get('b', 0)                                                                                                                      
                                                                                                                                                  
      # Evaluate expressions if strings                                                                                                           
      if isinstance(r, str):                                                                                                                      
          r = evaluate_color_expression(r, current_r, current_g, current_b, 'r')                                                                  
      # ... same for g, b                                                                                                                         
                                                                                                                                                  
      # Output to LED/COB                                                                                                                         
      led_controller.set_color(int(r), int(g), int(b))                                                                                            
                                                                                                                                                  
  ---                                                                                                                                             
  7. Animated State: _execute_animated_state(params)                                                                                              
                                                                                                                                                  
  Location: apps/raspi/output/light_states.py:186                                                                                                 
                                                                                                                                                  
  def _execute_animated_state(params):                                                                                                            
      state_machine_ref.stop_interval()                                                                                                           
                                                                                                                                                  
      speed = params.get('speed', 50)  # ms per frame                                                                                             
      r_expr, g_expr, b_expr = params.get('r'), params.get('g'), params.get('b')                                                                  
                                                                                                                                                  
      # Create expression functions                                                                                                               
      r_fn = create_safe_expression_function(r_expr)                                                                                              
      g_fn = create_safe_expression_function(g_expr)                                                                                              
      b_fn = create_safe_expression_function(b_expr)                                                                                              
                                                                                                                                                  
      frame = [0]                                                                                                                                 
      start_time = time.time()                                                                                                                    
                                                                                                                                                  
      def animation_fn():                                                                                                                         
          elapsed_ms = int((time.time() - start_time) * 1000)                                                                                     
          context = {'r': r, 'g': g, 'b': b, 't': elapsed_ms, 'frame': frame[0]}                                                                  
                                                                                                                                                  
          new_r = r_fn(context)  # Evaluate "sin(frame * 0.1) * 127 + 128"                                                                        
          new_g = g_fn(context)                                                                                                                   
          new_b = b_fn(context)                                                                                                                   
                                                                                                                                                  
          led_controller.set_color(int(new_r), int(new_g), int(new_b))                                                                            
          frame[0] += 1                                                                                                                           
                                                                                                                                                  
      # Start interval loop                                                                                                                       
      state_machine_ref.start_interval(animation_fn, speed)                                                                                       
                                                                                                                                                  
  ---                                                                                                                                             
  8. COB LED Output: COBLEDController.set_color()                                                                                                 
                                                                                                                                                  
  Location: apps/raspi/hardware/cobled/cobled.py:122                                                                                              
                                                                                                                                                  
  def set_color(self, r: int, g: int, b: int):                                                                                                    
      # Scale RGB to duty cycle (0-255 → 0-max_duty_cycle)                                                                                        
      r_duty = self._scale_to_duty(r)                                                                                                             
      g_duty = self._scale_to_duty(g)                                                                                                             
      b_duty = self._scale_to_duty(b)                                                                                                             
                                                                                                                                                  
      # Set PWM duty cycle on each GPIO pin                                                                                                       
      self.red_pwm.ChangeDutyCycle(r_duty)                                                                                                        
      self.green_pwm.ChangeDutyCycle(g_duty)                                                                                                      
      self.blue_pwm.ChangeDutyCycle(b_duty)                                                                                                       
                                                                                                                                                  
      self.current_color = (r, g, b)                                                                                                              
                                                                                                                                                  
  ---                                                                                                                                             
  Complete Data Flow Diagram                                                                                                                      
                                                                                                                                                  
  ┌─────────────────────────────────────────────────────────────────────┐                                                                         
  │                         USER INPUT                                   │                                                                        
  ├─────────────────────────────────────────────────────────────────────┤                                                                         
  │  Button Press              │  Voice Command                          │                                                                        
  │  (GPIO interrupt)          │  (Record button → STT)                  │                                                                        
  └──────────┬─────────────────┴──────────────┬─────────────────────────┘                                                                         
             │                                 │                                                                                                  
             ▼                                 ▼                                                                                                  
  ┌──────────────────────┐         ┌──────────────────────────────┐                                                                               
  │ _handle_button(evt)  │         │ smgen.process(text)          │                                                                               
  │ smgen.trigger(evt)   │         │   └─ AgentProcessor.run()    │                                                                               
  └──────────┬───────────┘         │      └─ Claude + Tools       │                                                                               
             │                     │         └─ createState()     │                                                                               
             │                     │         └─ appendRules()     │                                                                               
             │                     │         └─ setState()        │                                                                               
             │                     └──────────────┬───────────────┘                                                                               
             │                                    │                                                                                               
             ▼                                    ▼                                                                                               
  ┌──────────────────────────────────────────────────────────────┐                                                                                
  │              state_machine.execute_transition()               │                                                                               
  │  1. Find matching rules (state + transition)                  │                                                                               
  │  2. Sort by priority                                          │                                                                               
  │  3. Evaluate conditions                                       │                                                                               
  │  4. Execute action expression                                 │                                                                               
  │  5. Execute pipeline (if any)                                 │                                                                               
  │  6. set_state(new_state)                                      │                                                                               
  └──────────────────────────────┬───────────────────────────────┘                                                                                
                                 │                                                                                                                
                                 ▼                                                                                                                
  ┌──────────────────────────────────────────────────────────────┐                                                                                
  │                    _execute_state(state_dict)                 │                                                                               
  │                              │                                │                                                                               
  │                              ▼                                │                                                                               
  │              execute_unified_state(params)                    │                                                                               
  │  ┌───────────────────────────┴───────────────────────────┐   │                                                                                
  │  │                                                        │   │                                                                               
  │  ▼                                                        ▼   │                                                                               
  │  speed=None?                                        speed=50? │                                                                               
  │  ┌─────────────────┐                        ┌─────────────────┐                                                                               
  │  │_execute_static_ │                        │_execute_animated│                                                                               
  │  │     state()     │                        │    _state()     │                                                                               
  │  │                 │                        │                 │                                                                               
  │  │evaluate_color_  │                        │create_safe_     │                                                                               
  │  │expression()     │                        │expression_fn()  │                                                                               
  │  │       │         │                        │       │         │                                                                               
  │  │       ▼         │                        │       ▼         │                                                                               
  │  │ r=255, g=0, b=0 │                        │ animation_fn()  │                                                                               
  │  └────────┬────────┘                        │  called every   │                                                                               
  │           │                                 │  {speed}ms      │                                                                               
  │           │                                 └────────┬────────┘                                                                               
  │           │                                          │                                                                                        
  │           └──────────────────┬───────────────────────┘                                                                                        
  │                              │                                                                                                                
  │                              ▼                                                                                                                
  │              led_controller.set_color(r, g, b)                                                                                                
  │                              │                                                                                                                
  │                              ▼                                                                                                                
  │              ┌───────────────┴───────────────┐                                                                                                
  │              │  COBLEDController             │                                                                                                
  │              │  - _scale_to_duty(r,g,b)      │                                                                                                
  │              │  - red_pwm.ChangeDutyCycle()  │                                                                                                
  │              │  - green_pwm.ChangeDutyCycle()│                                                                                                
  │              │  - blue_pwm.ChangeDutyCycle() │                                                                                                
  │              └───────────────────────────────┘                                                                                                
  └──────────────────────────────────────────────────────────────┘                                                                                
                                                                                                                                                  
  ---                                                                                                                                             
  Key Global Variables (light_states.py)                                                                                                          
  ┌───────────────────────────┬──────────────────────┬─────────────────────────────────────┐                                                      
  │         Variable          │        Set By        │              Used For               │                                                      
  ├───────────────────────────┼──────────────────────┼─────────────────────────────────────┤                                                      
  │ led_controller            │ set_led_controller() │ Output RGB to hardware              │                                                      
  ├───────────────────────────┼──────────────────────┼─────────────────────────────────────┤                                                      
  │ state_machine_ref         │ set_state_machine()  │ Animation interval, stop_interval() │                                                      
  ├───────────────────────────┼──────────────────────┼─────────────────────────────────────┤                                                      
  │ voice_reactive_controller │ set_voice_reactive() │ Mic-reactive brightness mode        │                                                      
  └───────────────────────────┴──────────────────────┴─────────────────────────────────────┘                                                      
                                                                                                 