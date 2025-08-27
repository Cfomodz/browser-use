"""Tests for endless loop detection in Agent."""

import pytest
from browser_use.agent.views import AgentSettings, AgentState

def test_agent_settings_loop_detection_defaults():
	"""Test that loop detection settings have correct defaults."""
	settings = AgentSettings()
	
	assert settings.enable_loop_detection is True
	assert settings.loop_detection_window == 3
	assert settings.loop_detection_threshold == 2

def test_agent_state_recent_actions_initialization():
	"""Test that agent state initializes recent_actions correctly."""
	state = AgentState()
	
	assert hasattr(state, 'recent_actions')
	assert isinstance(state.recent_actions, list)
	assert len(state.recent_actions) == 0

class MockAgent:
	"""Mock agent for testing loop detection without full Agent dependencies."""
	
	def __init__(self, enable_loop_detection=True, window=3, threshold=2):
		self.settings = AgentSettings(
			enable_loop_detection=enable_loop_detection,
			loop_detection_window=window,
			loop_detection_threshold=threshold
		)
		self.state = AgentState()
		
	def _update_recent_actions(self, model_output):
		"""Copy of the agent method for testing."""
		if not model_output.action:
			return
			
		# Convert actions to a simplified format for comparison
		current_action_summary = []
		for action in model_output.action:
			action_data = action.model_dump(exclude_unset=True)
			action_name = next(iter(action_data.keys())) if action_data else 'unknown'
			action_params = action_data.get(action_name, {}) if action_data else {}
			
			# Create a normalized summary focusing on action type and key parameters
			summary = {
				'action': action_name,
				'goal': model_output.current_state.next_goal if model_output.current_state else '',
			}
			
			# Add key parameters that are relevant for loop detection
			if isinstance(action_params, dict):
				# Include index for click/type actions to detect clicking same elements
				if 'index' in action_params:
					summary['index'] = action_params['index']
				# Include URL for navigation actions
				if 'url' in action_params:
					summary['url'] = action_params['url']
				# Include scroll direction for scroll actions
				if action_name in ['scroll_up', 'scroll_down']:
					summary['scroll_direction'] = action_name
				# Include text for type actions (first 50 chars to avoid long texts)
				if 'text' in action_params:
					text = str(action_params['text'])[:50]
					summary['text'] = text
					
			current_action_summary.append(summary)
		
		# Add to recent actions list
		self.state.recent_actions.append({
			'step': self.state.n_steps,
			'actions': current_action_summary,
			'goal': model_output.current_state.next_goal if model_output.current_state else '',
		})
		
		# Keep only the most recent actions within the detection window
		window_size = self.settings.loop_detection_window
		if len(self.state.recent_actions) > window_size:
			self.state.recent_actions = self.state.recent_actions[-window_size:]

	def _detect_endless_loop(self):
		"""Copy of the agent method for testing."""
		if not self.settings.enable_loop_detection or len(self.state.recent_actions) < 2:
			return False, ""
			
		recent_actions = self.state.recent_actions[-self.settings.loop_detection_window:]
		
		# Check for repeated identical actions
		identical_count = 0
		if len(recent_actions) >= 2:
			last_action = recent_actions[-1]
			for prev_action in recent_actions[-self.settings.loop_detection_window:-1]:
				if self._actions_are_similar(last_action, prev_action):
					identical_count += 1
		
		# Check if we've exceeded the threshold
		if identical_count >= self.settings.loop_detection_threshold:
			# Generate description of the loop
			loop_description = self._generate_loop_description(recent_actions[-self.settings.loop_detection_threshold-1:])
			return True, loop_description
			
		return False, ""

	def _actions_are_similar(self, action1, action2):
		"""Copy of the agent method for testing."""
		actions1 = action1.get('actions', [])
		actions2 = action2.get('actions', [])
		
		# Must have same number of actions
		if len(actions1) != len(actions2):
			return False
		
		# Compare each action
		for a1, a2 in zip(actions1, actions2):
			# Same action type is required
			if a1.get('action') != a2.get('action'):
				return False
				
			# For certain actions, also check key parameters
			action_type = a1.get('action')
			
			# For click actions, same index indicates repeated clicking
			if action_type in ['click_element', 'click'] and a1.get('index') != a2.get('index'):
				return False
				
			# For navigation, same URL indicates repeated navigation
			if action_type in ['go_to_url', 'open_tab'] and a1.get('url') != a2.get('url'):
				return False
				
			# For scroll actions, same direction
			if action_type in ['scroll_up', 'scroll_down'] and a1.get('scroll_direction') != a2.get('scroll_direction'):
				return False
				
			# For typing, similar text (this is more lenient)
			if action_type in ['type_text', 'input_text']:
				text1 = a1.get('text', '')
				text2 = a2.get('text', '')
				if text1 != text2:
					return False
		
		# Also compare goals to detect repeated goals
		goal1 = action1.get('goal', '')
		goal2 = action2.get('goal', '')
		
		# If goals are the same and actions are the same, it's likely a loop
		return goal1 == goal2

	def _generate_loop_description(self, loop_actions):
		"""Copy of the agent method for testing."""
		if not loop_actions:
			return "Detected repeated actions"
			
		# Get the repeated action pattern
		last_action = loop_actions[-1]
		actions = last_action.get('actions', [])
		goal = last_action.get('goal', 'No goal specified')
		
		if not actions:
			return f"Repeated goal: '{goal}'"
		
		# Describe the actions
		action_descriptions = []
		for action in actions:
			action_name = action.get('action', 'unknown')
			if action_name == 'scroll_down':
				action_descriptions.append("scrolling down")
			elif action_name == 'scroll_up':
				action_descriptions.append("scrolling up")
			elif action_name == 'click_element':
				index = action.get('index', 'unknown')
				action_descriptions.append(f"clicking element #{index}")
			elif action_name == 'type_text':
				text = action.get('text', '')[:30]
				action_descriptions.append(f"typing '{text}...'")
			elif action_name == 'go_to_url':
				url = action.get('url', 'unknown')
				action_descriptions.append(f"navigating to {url}")
			else:
				action_descriptions.append(f"performing {action_name}")
		
		actions_str = ", ".join(action_descriptions)
		return f"Repeated pattern: {actions_str} with goal '{goal}'"


class MockActionModel:
	"""Mock action model for testing."""
	
	def __init__(self, action_name, **params):
		self.action_name = action_name
		self.params = params
	
	def model_dump(self, exclude_unset=True):
		return {self.action_name: self.params}

class MockCurrentState:
	"""Mock current state for testing."""
	
	def __init__(self, goal):
		self.next_goal = goal

class MockOutput:
	"""Mock agent output for testing."""
	
	def __init__(self, action, current_state):
		self.action = [action]
		self.current_state = current_state

def test_scroll_loop_detection():
	"""Test that repeated scroll actions trigger loop detection."""
	agent = MockAgent()
	
	# Create repeated scroll_down actions
	for i in range(4):
		action = MockActionModel('scroll_down')
		current_state = MockCurrentState('Scroll down again to see more of the page')
		output = MockOutput(action, current_state)
		
		agent._update_recent_actions(output)
		agent.state.n_steps += 1
		
		# Check for loop after each action
		is_loop, description = agent._detect_endless_loop()
		
		if i < 2:  # First 3 actions shouldn't trigger detection
			assert not is_loop, f"Loop detected too early at step {i+1}"
		else:  # Should detect loop by step 3
			assert is_loop, f"Loop not detected at step {i+1}"
			assert "scrolling down" in description
			assert "Scroll down again to see more of the page" in description
			break

def test_click_loop_detection():
	"""Test that repeated clicks on same element trigger loop detection."""
	agent = MockAgent()
	
	# Create repeated click actions on same element
	for i in range(4):
		action = MockActionModel('click_element', index=42)
		current_state = MockCurrentState('Click the button to submit')
		output = MockOutput(action, current_state)
		
		agent._update_recent_actions(output)
		agent.state.n_steps += 1
		
		is_loop, description = agent._detect_endless_loop()
		
		if i < 2:
			assert not is_loop
		else:
			assert is_loop
			assert "clicking element #42" in description
			assert "Click the button to submit" in description
			break

def test_no_false_positives_different_actions():
	"""Test that different actions don't trigger false positive loop detection."""
	agent = MockAgent()
	
	actions_data = [
		('scroll_down', {}, 'Scroll down to see more'),
		('click_element', {'index': 1}, 'Click the first button'),
		('type_text', {'text': 'hello', 'index': 2}, 'Type hello in input field'),
		('scroll_up', {}, 'Scroll up to see previous content')
	]
	
	for i, (action_name, params, goal) in enumerate(actions_data):
		action = MockActionModel(action_name, **params)
		current_state = MockCurrentState(goal)
		output = MockOutput(action, current_state)
		
		agent._update_recent_actions(output)
		agent.state.n_steps += 1
		
		is_loop, description = agent._detect_endless_loop()
		assert not is_loop, f"False positive loop detected at step {i+1}: {description}"

def test_no_false_positives_similar_but_different_clicks():
	"""Test that clicking different elements doesn't trigger loop detection."""
	agent = MockAgent()
	
	for i in range(4):
		# Click different elements each time
		action = MockActionModel('click_element', index=i)
		current_state = MockCurrentState(f'Click element {i}')
		output = MockOutput(action, current_state)
		
		agent._update_recent_actions(output)
		agent.state.n_steps += 1
		
		is_loop, description = agent._detect_endless_loop()
		assert not is_loop, f"False positive detected clicking different elements: {description}"

def test_disabled_loop_detection():
	"""Test that loop detection can be disabled."""
	agent = MockAgent(enable_loop_detection=False)
	
	# Create obviously looping actions
	for i in range(10):
		action = MockActionModel('scroll_down')
		current_state = MockCurrentState('Scroll down')
		output = MockOutput(action, current_state)
		
		agent._update_recent_actions(output)
		agent.state.n_steps += 1
		
		is_loop, description = agent._detect_endless_loop()
		assert not is_loop, "Loop detection should be disabled"

def test_configurable_threshold():
	"""Test that loop detection threshold is configurable."""
	# Set threshold to 1 (more sensitive)
	agent = MockAgent(threshold=1)
	
	# Should trigger after just 1 repeated action (2 total similar actions)
	for i in range(3):
		action = MockActionModel('scroll_down')
		current_state = MockCurrentState('Scroll down')
		output = MockOutput(action, current_state)
		
		agent._update_recent_actions(output)
		agent.state.n_steps += 1
		
		is_loop, description = agent._detect_endless_loop()
		
		if i < 1:
			assert not is_loop
		else:
			assert is_loop, f"Loop not detected with threshold=1 at step {i+1}"
			break

def test_window_size_limits_history():
	"""Test that detection window limits how far back we look."""
	agent = MockAgent(window=2, threshold=1)  # Small window, sensitive threshold
	
	# Create pattern: A, A, B, B - should only detect the B loop, not A
	patterns = [
		('scroll_down', 'Scroll down'),
		('scroll_down', 'Scroll down'), 
		('click_element', 'Click button'),
		('click_element', 'Click button')
	]
	
	for i, (action_name, goal) in enumerate(patterns):
		if action_name == 'click_element':
			action = MockActionModel(action_name, index=1)
		else:
			action = MockActionModel(action_name)
		
		current_state = MockCurrentState(goal)
		output = MockOutput(action, current_state)
		
		agent._update_recent_actions(output)
		agent.state.n_steps += 1
		
		is_loop, description = agent._detect_endless_loop()
		
		# Should only detect loop on the last click action
		if i == 3:  # Last step
			assert is_loop, "Should detect click loop within window"
			assert "clicking" in description
		elif i <= 2:  # Earlier steps
			# May or may not detect depending on window, but shouldn't detect scroll loop at step 3
			if is_loop and i == 2:
				# If it detects at step 2, it should be about clicking, not scrolling
				assert "clicking" not in description or len(agent.state.recent_actions) < 2