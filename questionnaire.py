import logging
import random

from user import User
from receptionist import Receptionist
from questions import question_goals
from prompt_builder import PromptBuilder
from storage import COL_INTERNAL_NOTES, COL_COMPLETION_TIME, COL_FULL_NAME

logger = logging.getLogger(__name__)


class QuestionnaireManager:
    user_input: str

    def __init__(self, user_id: str, user_input: str, store=None):
        """
        :param user_id: Unique id which must appear in the store.
        :param user_input: Any text the user has input in chat or ''.
        :param store: Storage backend passed through to ``User``.
        :raises ValueError: ("User not found") if user_id is not in the store.
        """
        self.user = User(user_id, store=store)
        self.user_input = user_input
        logger.debug("Questionnaire resumed for user %s", user_id)

        # add user input to history
        if user_input is not None and len(user_input):
            self.user.add_to_current_convo(user_input, True)
            self.user.save()

    def get_random_intro_text(self) -> str:
        possible_intros = [
            "How kind of you to join us today. May I know the full name your booking is under?",
            "I'm glad you found a cozy seat! May I know your full name to locate your appointment details, please?",
            "I'm so glad to see you're settled. May I please have your full name to confirm your booking?",
            "Oh, it seems you have found a comfortable spot. Excellent! Now, could I kindly ask for your full name for our record?",
            "It's wonderful to see you making yourself comfortable. May I kindly ask your full name to ensure that I'm assisting the correct person?",
            "Great! I see you've found a perfect spot amidst this tranquil forest scenery. Now that you're settled in, may I have your full name for our records, please?",
            "Ah, I see you have found a comfy spot! To ensure I have your correct details, may I know your full name, please?",
            "I can see you've found a comfy spot, perfect! May I ask your full name please, so I can ensure everything's set just right for your session?",
            "I'm delighted to see you settling in. Could you kindly share your full name, so I can ensure our records are accurate?",
        ]
        return random.choice(possible_intros)

    def return_fixed_starting_response(self, q_idx: int):
        fixed_response = {
            "users_answer_to_goal": None,
            "history_to_add": None,
            "internal_comment": None,
            "amys_response": self.get_random_intro_text(),
            "should_ask_next_question": False,
        }
        self.user.clear_current_convo()  # clear current convo for clarity
        amys_response = self.process_llm_response(fixed_response)
        return amys_response, "No prompt - intro question.", q_idx

    def next(self):
        """
        Collects user data, and returns the response for the current question.
        :raises ResponseError: if the LLM didn't reply in the correct format.
        :raises openai.RateLimitError: if the quota is exceeded.
        :return: Amy's response, the prompt used, and the current question index.
        """
        q_idx = self.user.get_current_progress()

        # If 1st question (full name) and no user input, return the starting
        # text manually as the model sometimes invents names otherwise.
        if q_idx <= COL_FULL_NAME and (not self.user_input or len(self.user_input) == 0):
            return self.return_fixed_starting_response(q_idx)

        current_goal = self.get_question_goal(q_idx)
        try:
            next_goal = self.get_question_goal(q_idx + 1)
            # Shorten the long upcoming prompt if it's the 'expectation' prompt.
            if next_goal.startswith("Find out what the user expects"):
                next_goal = "Find out what the user expects from their time at Intermission."
        except IndexError:
            next_goal = "No more goals."

        is_user_rejoining_session = False

        # Gather the current conversation for this goal so far.
        current_goal_conversation = self.user.get_current_convo()
        if current_goal_conversation == "":
            if q_idx == COL_FULL_NAME:
                # For the first question, share the initial prompt everyone gets.
                current_goal_conversation = """Amy: Hello and welcome to your Intermission. My name is Amy and it's my pleasure to assist you!

Please find a comfortable seat while I find your appointment details."""
                current_goal_conversation += "User: *sits*"
            else:
                current_goal_conversation = "User: (none yet)"
                if q_idx >= COL_FULL_NAME + 1:
                    current_goal += " Mention resuming the session. The user is back again, but hasn't answered the current question yet."
                    is_user_rejoining_session = True  # no current conversation

        history = self.user.get_history()
        logger.debug("Current goal: [%s] %s", q_idx, current_goal)

        # If the conversation was carried on (e.g. page reload) we need to insert
        # a user message, otherwise the model will output the User's response.
        if q_idx > COL_FULL_NAME:
            last_response = self.check_last_response(current_goal_conversation)
            if last_response == "Amy":
                current_goal_conversation += "\nUser: (refreshed the page - so welcome them back (if not already) and ask again the current goal question.)"
                is_user_rejoining_session = True

        prompt = PromptBuilder.build_prompt(
            current_goal, next_goal, current_goal_conversation, history
        )

        llm_json = Receptionist.prompt(prompt)
        logger.debug("LLM response: %s", llm_json)

        # The model sometimes wrongly advances the goal when the user is
        # rejoining and hasn't actually answered yet — override it here.
        if is_user_rejoining_session and llm_json["should_ask_next_question"] is True:
            llm_json["should_ask_next_question"] = False
            logger.debug("Corrected should_ask_next_question to False (rejoining)")

        # The opening exchange is rocky; don't advance before the name is given.
        if q_idx == COL_FULL_NAME:
            if llm_json["users_answer_to_goal"] is None and llm_json["should_ask_next_question"] is True:
                llm_json["should_ask_next_question"] = False
                logger.debug("Corrected initial should_ask_next_question to False")

        amys_response = self.process_llm_response(llm_json)
        return amys_response, prompt, q_idx

    def check_last_response(self, conversation: str):
        """Return whether 'Amy' or 'User' spoke last in the conversation string."""
        last_amy_index = conversation.rfind("Amy:")
        last_user_index = conversation.rfind("User:")

        if last_amy_index > last_user_index:
            return "Amy"
        elif last_user_index > last_amy_index:
            return "User"
        return None

    def process_llm_response(self, data: dict):
        # Save answer if we have one.
        if data["users_answer_to_goal"]:
            self.user.set_current_answer(data["users_answer_to_goal"])

        # Save key info about the user.
        if data["history_to_add"]:
            self.user.add_history(data["history_to_add"])

        if data["internal_comment"]:
            self.user.append_answer(COL_INTERNAL_NOTES, data["internal_comment"])

        # Normalise stray quoting around the experience name.
        amys_response = data["amys_response"]
        amys_response = amys_response.replace("'Intermission,'", "Intermission")
        amys_response = amys_response.replace("'Intermission.'", "Intermission")
        amys_response = amys_response.replace("'Intermission'", "Intermission")

        if data["should_ask_next_question"]:
            new_idx = self.user.get_current_progress() + 1
            self.user.set_progress(new_idx)
            self.user.clear_current_convo()
            self.user.add_to_current_convo(amys_response, False)
        else:
            self.user.add_to_current_convo(amys_response, False)

        # End the conversation once the final goal is reached.
        if self.user.get_current_progress() >= COL_COMPLETION_TIME:
            self.user.set_end_time()

        self.user.save()
        return amys_response

    def get_question_goal(self, idx: int):
        if idx < 0 or idx >= len(question_goals):
            raise IndexError("Question index out of range.")
        return question_goals[idx]

    def return_completed_response(self):
        name = self.user.answers[COL_FULL_NAME]
        if len(name):
            name = " " + name
        fixed = f"Thank you for your time{name}. You have completed the questionnaire. I hope you enjoy your experience at Intermission!"
        self.user.add_to_current_convo(fixed + "- (Fixed response when user completes)", False)
        self.user.set_end_time()
        self.user.save()
        return fixed, "", COL_COMPLETION_TIME
