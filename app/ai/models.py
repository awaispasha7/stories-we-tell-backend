"""
AI Model Management System
Handles multiple AI providers based on task type as specified by client requirements.
"""

import os
from typing import Dict, Any, Optional
from enum import Enum
from dotenv import load_dotenv

load_dotenv()

# Try to import AI packages with error handling
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError as e:
    print(f"Warning: OpenAI not available: {e}")
    OPENAI_AVAILABLE = False

try:
    from google import genai
    from google.genai import types as genai_types
    GEMINI_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Gemini not available: {e}")
    GEMINI_AVAILABLE = False
    genai = None
    genai_types = None

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Anthropic not available: {e}")
    ANTHROPIC_AVAILABLE = False

class TaskType(Enum):
    """Task types for AI model selection"""
    CHAT = "chat"
    DESCRIPTION = "description"
    SCRIPT = "script"
    SCENE = "scene"

class AIModelManager:
    """Manages AI model selection and execution based on task type"""
    
    def __init__(self):
        # Initialize OpenAI
        openai.api_key = os.getenv("OPENAI_API_KEY")

        # Check if other API keys are available and initialize if they are
        gemini_key = os.getenv("GEMINI_API_KEY")
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")

        if gemini_key and gemini_key != "your_gemini_api_key_here":
            try:
                self.gemini_client = genai.Client(api_key=gemini_key)
                self.gemini_available = True
            except Exception as e:
                print(f"Warning: Failed to initialize Gemini client: {e}")
                self.gemini_available = False
        else:
            self.gemini_available = False

        if anthropic_key and anthropic_key != "your_anthropic_api_key_here":
            self.claude_client = anthropic.Anthropic(api_key=anthropic_key)
            self.claude_available = True
        else:
            self.claude_available = False

        # Model selection mapping - using latest recommended models
        self.model_mapping = {
            TaskType.CHAT: "gpt-4.1-mini",  # Best price-to-quality for high-traffic chat
            TaskType.DESCRIPTION: "gemini-2.5-flash",  # Best price-performance model for creative reasoning
            TaskType.SCRIPT: "claude-sonnet-4-5-20250929",  # Latest Claude Sonnet 4.5 (per Anthropic API docs)
            TaskType.SCENE: "gpt-4.1",  # Flagship for deep text generation
        }
    
    def _build_conversation_context(self, conversation_history: list, image_context: str = "") -> str:
        """Build conversation context for the system prompt"""
        if not conversation_history:
            return "This is the start of our conversation."
        
        # Extract key information from conversation
        context_parts = []
        
        # Look for character names
        characters = set()
        for msg in conversation_history:
            content = msg.get('content', '').lower()
            # Simple character name detection (could be enhanced)
            if 'my character' in content or 'main character' in content:
                # Extract potential character names
                words = content.split()
                for i, word in enumerate(words):
                    if word in ['character', 'protagonist', 'main'] and i + 2 < len(words):
                        if words[i+1] == 'is' or words[i+1] == 'named':
                            characters.add(words[i+2].title())
        
        if characters:
            context_parts.append(f"Characters mentioned: {', '.join(characters)}")
        
        # Look for story elements
        story_elements = []
        for msg in conversation_history:
            content = msg.get('content', '').lower()
            if any(keyword in content for keyword in ['story', 'plot', 'setting', 'genre', 'time', 'place']):
                story_elements.append("Story details have been discussed")
                break
        
        if story_elements:
            context_parts.append("Story development is in progress")
        
        # Add image context if available
        if image_context:
            context_parts.append(f"Visual context: {image_context}")
        
        return " | ".join(context_parts) if context_parts else "Conversation in progress"

    def is_story_complete(self, dossier_context: dict) -> bool:
        """Check if story is complete based on filled slots"""
        if not dossier_context:
            return False
        
        # Required slots for story completion
        required_slots = [
            'story_timeframe',
            'story_location', 
            'story_world_type',
            'subject_full_name',
            'problem_statement',
            'actions_taken',
            'outcome'
        ]
        
        # Check if all required slots are filled (not "Unknown")
        filled_slots = 0
        for slot in required_slots:
            value = dossier_context.get(slot, 'Unknown')
            if value and value != 'Unknown' and value.strip():
                filled_slots += 1
        
        # Story is complete if 80% of required slots are filled
        completion_rate = filled_slots / len(required_slots)
        is_complete = completion_rate >= 0.8
        
        print(f"📊 Story completion check: {filled_slots}/{len(required_slots)} slots filled ({completion_rate:.1%}) - {'COMPLETE' if is_complete else 'INCOMPLETE'}")
        return is_complete

    async def generate_response(self, task_type: TaskType, prompt: str, **kwargs) -> Dict[str, Any]:
        """
        Generate response using the appropriate AI model for the task type
        
        Args:
            task_type: The type of task (determines which model to use)
            prompt: The input prompt
            **kwargs: Additional parameters for the specific model
            
        Returns:
            Dict containing the response and metadata
        """
        try:
            if task_type == TaskType.CHAT:
                return await self._generate_chat_response(prompt, **kwargs)
            elif task_type == TaskType.DESCRIPTION:
                return await self._generate_description_response(prompt, **kwargs)
            elif task_type == TaskType.SCRIPT:
                return await self._generate_script_response(prompt, **kwargs)
            elif task_type == TaskType.SCENE:
                return await self._generate_scene_response(prompt, **kwargs)
            else:
                raise ValueError(f"Unknown task type: {task_type}")
                
        except Exception as e:
            return {
                "response": f"Error generating response: {str(e)}",
                "model_used": self.model_mapping.get(task_type, "unknown"),
                "error": str(e)
            }
    
    async def _generate_chat_response(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Generate chat response using GPT-5 mini as specified by client"""
        try:
            print(f"🤖 Attempting to call OpenAI with model: gpt-4o-mini")
            print(f"🤖 Prompt: '{prompt[:100]}...'")
            
            # Check for RAG context (includes user messages, documents, and global knowledge)
            rag_context = kwargs.get("rag_context")
            rag_context_text = ""
            
            if rag_context:
                # Include combined RAG context (user messages + documents + global knowledge)
                if rag_context.get("combined_context_text"):
                    rag_context_text = f"\n\n## RELEVANT CONTEXT FROM YOUR PREVIOUS CONVERSATIONS:\n{rag_context.get('combined_context_text')}\n"
                    print(f"📚 Including RAG context: {rag_context.get('user_context_count', 0)} user messages, {rag_context.get('document_context_count', 0)} document chunks, {rag_context.get('global_context_count', 0)} global patterns")
                else:
                    # Fallback: build lightweight context if items exist but combined text wasn't provided
                    uc = rag_context.get("user_context") or []
                    dc = rag_context.get("document_context") or []
                    gc = rag_context.get("global_context") or []
                    if uc or dc or gc:
                        parts = []
                        if uc:
                            parts.append("## Relevant User Messages:")
                            for i, item in enumerate(uc[:5], 1):
                                snippet = item.get("content") or item.get("content_snippet") or ""
                                parts.append(f"{i}. {snippet[:200]}...")
                            parts.append("")
                        if dc:
                            parts.append("## Relevant Document Chunks:")
                            for i, item in enumerate(dc[:5], 1):
                                chunk = item.get("chunk_text", "")
                                parts.append(f"{i}. {chunk[:200]}...")
                            parts.append("")
                        if gc:
                            parts.append("## Relevant Knowledge:")
                            for i, item in enumerate(gc[:3], 1):
                                example = item.get("example_text", "")
                                parts.append(f"{i}. {example[:150]}...")
                            parts.append("")
                        rag_context_text = "\n\n" + "\n".join(parts)
                        print(f"📚 Built fallback RAG context: user={len(uc)} doc={len(dc)} global={len(gc)}")
                    else:
                        print(f"⚠️ RAG context present but empty items")
            
            # Check for active revision request and get revision prompt
            revision_prompt = ""
            project_id = kwargs.get("project_id")
            if project_id:
                try:
                    from ..services.revision_prompt_library import get_active_revision_prompt
                    revision_prompt = await get_active_revision_prompt(str(project_id))
                    if revision_prompt:
                        print(f"🔄 [REVISION] Active revision prompt found for project {project_id}")
                except Exception as rev_e:
                    print(f"⚠️ [REVISION] Error fetching revision prompt: {rev_e}")
            
            # Check for dossier context (existing story data) - Updated for client requirements
            dossier_context = kwargs.get("dossier_context")
            dossier_info = ""
            if dossier_context:
                dossier_info = "\n\nEXISTING STORY DATA (Slot-based):\n"
                
                # Story Frame
                if dossier_context.get('story_timeframe') and dossier_context.get('story_timeframe') != 'Unknown':
                    dossier_info += f"Time: {dossier_context['story_timeframe']}\n"
                if dossier_context.get('story_location') and dossier_context.get('story_location') != 'Unknown':
                    dossier_info += f"Location: {dossier_context['story_location']}\n"
                if dossier_context.get('story_world_type') and dossier_context.get('story_world_type') != 'Unknown':
                    dossier_info += f"World Type: {dossier_context['story_world_type']}\n"
                
                # Heroes (Primary Characters)
                if dossier_context.get('heroes') and isinstance(dossier_context['heroes'], list) and len(dossier_context['heroes']) > 0:
                    for i, hero in enumerate(dossier_context['heroes'], 1):
                        if hero.get('name'):
                            dossier_info += f"Hero {i}: {hero.get('name')}"
                            if hero.get('age_at_story'):
                                dossier_info += f" (age {hero.get('age_at_story')})"
                            if hero.get('relationship_to_user'):
                                dossier_info += f", {hero.get('relationship_to_user')}"
                            # Include photo status - CRITICAL for checking if photos already exist
                            if hero.get('photo_url') and hero.get('photo_url').strip():
                                dossier_info += f" [PHOTO EXISTS: {hero.get('photo_url')}]"
                            dossier_info += "\n"
                
                # Supporting Characters
                if dossier_context.get('supporting_characters') and isinstance(dossier_context['supporting_characters'], list) and len(dossier_context['supporting_characters']) > 0:
                    for char in dossier_context['supporting_characters']:
                        if char.get('name'):
                            dossier_info += f"Supporting: {char.get('name')}"
                            if char.get('role'):
                                dossier_info += f" ({char.get('role')})"
                            # Include photo status - CRITICAL for checking if photos already exist
                            if char.get('photo_url') and char.get('photo_url').strip():
                                dossier_info += f" [PHOTO EXISTS: {char.get('photo_url')}]"
                            dossier_info += "\n"
                
                # Story Type & Perspective
                if dossier_context.get('story_type') and dossier_context.get('story_type') != 'other':
                    dossier_info += f"Story Type: {dossier_context['story_type']}\n"
                if dossier_context.get('perspective') and dossier_context.get('perspective') != 'narrator_voice':
                    dossier_info += f"Perspective: {dossier_context['perspective']}\n"
                if dossier_context.get('audience'):
                    aud = dossier_context['audience']
                    if isinstance(aud, dict):
                        if aud.get('who_will_see_first'):
                            dossier_info += f"Audience: {aud.get('who_will_see_first')}\n"
                        if aud.get('desired_feeling'):
                            dossier_info += f"Desired Feeling: {aud.get('desired_feeling')}\n"
                
                # Character (Subject - Legacy)
                if dossier_context.get('subject_full_name') and dossier_context.get('subject_full_name') != 'Unknown':
                    dossier_info += f"Character: {dossier_context['subject_full_name']}\n"
                if dossier_context.get('subject_relationship_to_writer') and dossier_context.get('subject_relationship_to_writer') != 'Unknown':
                    dossier_info += f"Relationship: {dossier_context['subject_relationship_to_writer']}\n"
                
                # Story Craft
                if dossier_context.get('problem_statement') and dossier_context.get('problem_statement') != 'Unknown':
                    dossier_info += f"Problem: {dossier_context['problem_statement']}\n"
                if dossier_context.get('actions_taken') and dossier_context.get('actions_taken') != 'Unknown':
                    dossier_info += f"Actions: {dossier_context['actions_taken']}\n"
                if dossier_context.get('outcome') and dossier_context.get('outcome') != 'Unknown':
                    dossier_info += f"Outcome: {dossier_context['outcome']}\n"
                
                # Technical
                if dossier_context.get('title') and dossier_context.get('title') != 'Untitled Story':
                    dossier_info += f"Title: {dossier_context['title']}\n"
                
                # MISSING INFORMATION CHECK - Help LLM identify what's missing
                missing_info = []
                
                # Check heroes
                heroes = dossier_context.get('heroes', [])
                if not heroes or len(heroes) == 0:
                    missing_info.append("At least one hero character (name, age, relationship, physical, personality)")
                else:
                    for idx, hero in enumerate(heroes, 1):
                        hero_name = hero.get('name', f'Hero {idx}')
                        if not hero.get('age_at_story') or hero.get('age_at_story') == 'Unknown':
                            missing_info.append(f"{hero_name}'s age at the time of the story")
                        if not hero.get('photo_url') or not hero.get('photo_url').strip():
                            missing_info.append(f"Photo for {hero_name} (optional but helpful)")
                
                # Check supporting characters (optional, but if mentioned should have basic info)
                supporting = dossier_context.get('supporting_characters', [])
                for char in supporting:
                    char_name = char.get('name', 'Supporting character')
                    if not char.get('photo_url') or not char.get('photo_url').strip():
                        missing_info.append(f"Photo for {char_name} (optional)")
                
                # Check setting
                if not dossier_context.get('story_location') or dossier_context.get('story_location') == 'Unknown':
                    missing_info.append("Story location (where does it take place?)")
                if not dossier_context.get('story_timeframe') or dossier_context.get('story_timeframe') == 'Unknown':
                    missing_info.append("Story timeframe (when does it take place?)")
                
                # Check story type
                story_type = dossier_context.get('story_type', '').strip().lower()
                if not story_type or story_type == 'other' or story_type == 'unknown':
                    missing_info.append("Story type (romantic, childhood drama, fantasy, epic/legend, adventure, historic action, documentary tone, or other)")
                
                # Check audience & perspective
                audience = dossier_context.get('audience', {})
                if not isinstance(audience, dict) or not audience.get('who_will_see_first'):
                    missing_info.append("Audience - who will see this first?")
                if not isinstance(audience, dict) or not audience.get('desired_feeling'):
                    missing_info.append("Desired feeling - what do you want them to feel?")
                if not dossier_context.get('perspective') or dossier_context.get('perspective') == 'Unknown':
                    missing_info.append("Story perspective (first_person, narrator_voice, legend_myth_tone, documentary_tone)")
                
                # Check story content
                if not dossier_context.get('problem_statement') or dossier_context.get('problem_statement') == 'Unknown':
                    missing_info.append("Problem statement (what's the main challenge?)")
                if not dossier_context.get('actions_taken') or dossier_context.get('actions_taken') == 'Unknown':
                    missing_info.append("Actions taken (what does the character do?)")
                if not dossier_context.get('outcome') or dossier_context.get('outcome') == 'Unknown':
                    missing_info.append("Story outcome (how does it end?)")
                
                # Add missing info section if there are missing fields
                if missing_info:
                    dossier_info += f"\n⚠️ MISSING INFORMATION (Ask for these naturally during conversation):\n"
                    for item in missing_info:
                        dossier_info += f"  - {item}\n"
                    dossier_info += "\nIMPORTANT: Ask for missing information naturally and contextually. Don't ask all at once - weave questions into the conversation flow. Use friendly language like 'Quick question - what's [character name]'s age?' or 'Just to make sure I have everything - where does this story take place?'\n"
                
                print(f"📋 Including dossier context: {dossier_context.get('title', 'Untitled')} - {len([k for k, v in dossier_context.items() if v and v != 'Unknown'])} slots filled, {len(missing_info)} missing fields")
            
            # Get authentication status from kwargs
            is_authenticated = kwargs.get("is_authenticated", False)
            
            # Build authentication-specific instructions
            auth_instructions = ""
            if is_authenticated:
                auth_instructions = """
        USER STATUS: The user is AUTHENTICATED (signed in). They can create unlimited stories and projects.
        - NEVER suggest signing up or creating an account
        - When they want a new story, say: "Great! Let's start a new story. What story idea is on your mind?"
        - After story completion, say: "Would you like to create another story? Just let me know what story idea you'd like to explore next!"
        """
            else:
                auth_instructions = """
        USER STATUS: The user is ANONYMOUS (not signed in). They are limited to one story.
        - When they want a new story, say: "I'd love to help you create another story! To create unlimited stories and save your progress, please sign up. It's free and takes just a moment!"
        - After story completion, suggest: "Would you like to create another story? Sign up to create unlimited stories and save your progress!"
        """
            
            # Enhanced story development system prompt based on client requirements
            system_prompt = f"""You are Ariel, a cinematic story development assistant for Stories We Tell. Your role is to help users develop compelling stories by following a structured, stateful conversation flow.

        CORE PRINCIPLES:
        1. CHARACTER-FIRST: Always start with "Who is the main character?"
        2. STATEFUL MEMORY: Remember all previous answers and build on them
        3. PRONOUN RESOLUTION: Track character names and resolve pronouns (he/she = character name)
        4. STORY COMPLETION: Recognize when story is complete and transition appropriately
        5. PROGRESSIVE DISCLOSURE: Move from problem → actions → outcome
        6. EXACT WORKFLOW ORDER: Follow the 8-step workflow exactly as specified - do not deviate

        CONVERSATION STRUCTURE (Slot-based, in EXACT order):
        1. STEP 1 - INITIAL QUESTION: Start with "Who is the main character of your story?" (This begins hero intake)
        2. STEP 2 - HERO CHARACTERS (Primary - up to 2):
           - For EACH hero, collect: name → age_at_story → relationship_to_user → physical_descriptors → personality_traits
           - DO NOT ask about photos yet - photos come later in Step 4
           - After first hero is complete, ask: "Is there a second hero in the story?" (if yes, collect full intake for hero #2)
        3. STEP 3 - SUPPORTING CHARACTERS (Secondary - up to 2):
           - Ask: "Are there other important people in the story?"
           - For each: name → role → description (light metadata only)
           - DO NOT ask about photos yet - photos come later in Step 4
        4. STEP 4 - PHOTO UPLOAD (Separate step after all characters):
           - AFTER all heroes and supporting characters are collected, check for photos:
           - CRITICAL: Check the dossier to see which characters already have photo_url set
           - Only ask about photos for characters that do NOT have a photo_url (or have empty photo_url)
           - For each hero WITHOUT photo_url: "Do you have a photo of [hero name]? You can upload it now or skip and we'll send you a link later."
           - For each supporting character WITHOUT photo_url (optional): "Do you have a photo of [character name]? (optional - you can skip)"
           - If a character already has a photo_url in the dossier, DO NOT ask about photos for that character again
           - User can: upload now or skip (link sent later)
        5. STEP 5 - SETTING & TIME:
           - Ask: "Where does the story happen?"
           - Ask: "What time period?"
           - Ask: "Season/time of year?"
           - Ask: "Any meaningful environmental details?"
           - Natural language. No structure required.
        6. STEP 6 - STORY TYPE: 
           - CRITICAL: You MUST explicitly ask the user to choose a story type
           - Present the options clearly: "What type of story do you want? Please choose one:
             • Romantic
             • Childhood drama
             • Fantasy
             • Epic/legend
             • Adventure
             • Historic action
             • Documentary tone
             • Other"
           - Wait for the user to explicitly choose one of these options
           - Map their response to the exact values: "romantic", "childhood_drama", "fantasy", "epic_legend", "adventure", "historic_action", "documentary_tone", "other"
           - If the user's response doesn't clearly match, ask them to choose from the list
        7. STEP 7 - AUDIENCE & PERSPECTIVE:
           - Ask: "Who will see this first?"
           - Ask: "What do you want them to feel?"
           - Ask: "What perspective?" (first_person, narrator_voice, legend_myth_tone, documentary_tone)
           - CRITICAL: You MUST ask ALL THREE questions in this order
        8. STEP 8 - STORY CONTENT COLLECTION (CRITICAL):
           - AFTER all setup steps are complete (characters, photos, setting, story type, audience), collect the ACTUAL STORY:
           - Ask: "What's the main problem or challenge [hero name] faces in this story?" (problem_statement)
           - Ask: "What does [hero name] do to address this problem or navigate this situation?" (actions_taken)
           - DO NOT skip to the ending until the story problem and actions have been collected
           - The story is just getting started at this point - you need to collect the story content first
        9. STEP 9 - OUTCOME (Only after story content is collected):
           - ONLY ask about the ending AFTER problem_statement and actions_taken have been collected
           - Ask: "How does the story end? What's the final outcome or resolution?" (outcome)
           - CRITICAL: Do NOT ask about the ending prematurely - wait until the story has been told
        10. STEP 10 - DATA PACKAGING: Bundle characters, photos, setting, tone & style, perspective, story content. Create Story Record. Store in RAG. Generate Story ID.
        11. COMPLETION: Recognize when story is complete
        
        CHARACTER COLLECTION PRIORITY:
        - ALWAYS collect HEROES first (primary characters)
        - Then ask about SUPPORTING CHARACTERS (secondary)
        - Heroes require full details (age, relationship, physical, personality)
        - Supporting characters need only light metadata (name, role, description)

        MEMORY MANAGEMENT:
        - ALWAYS reference previous answers by name
        - NEVER re-ask questions already answered
        - Use character names consistently (never use pronouns without context)
        - Show you remember: "You mentioned [character name] earlier..."

        PRONOUN RESOLUTION:
        - When user says "he" or "she", always connect to the established character name
        - Example: "So [Character Name] faces this challenge. What does [Character Name] do to overcome it?"
        - NEVER ask "Who is he/she?" if character name is already established

        PROACTIVE INFORMATION GATHERING (CRITICAL):
        - BEFORE allowing story completion, you MUST check the dossier context for missing required information
        - Required fields that MUST be collected before story completion:
          * Heroes: name, age_at_story (CRITICAL - cannot be "Unknown" or empty), relationship_to_user, physical_descriptors, personality_traits
          * Supporting Characters: name, role, description (if mentioned)
          * Setting: story_location, story_timeframe (cannot be "Unknown")
          * Story Type: story_type (must be explicitly chosen, not "other" unless user explicitly chooses it)
          * Audience: who_will_see_first, desired_feeling (both required)
          * Perspective: perspective (cannot be "Unknown")
          * Story Content: problem_statement, actions_taken, outcome (all required)
        - NATURALLY ask for missing information during the conversation, not just at the end
        - When you notice missing information, ask about it contextually and naturally:
          * Example: "I want to make sure I have all the details. What's Mira's age at the time of this story?"
          * Example: "Quick question - do you have a photo of [character name]? It helps us visualize them better."
          * Example: "Just to clarify - where exactly does this story take place?"
        - Ask ONE missing piece at a time, naturally woven into the conversation flow
        - Use friendly, conversational language - don't sound like a form
        - If the user says "I don't know" or "not sure", acknowledge it and move on (mark as optional if appropriate)
        - CRITICAL: Do NOT allow story completion if required fields are missing - ask for them first

        STORY COMPLETION DETECTION:
        - Look for phrases: "at the end", "finally", "in conclusion", "that's the story", "that's my story", "story complete", "i'm done", "finished", "that's all", "the end"
        - When story seems complete, FIRST check if all required information is collected
        - If required fields are missing, acknowledge the story content but say: "Before we wrap up, I just need a couple more details to complete your story dossier..."
        - Then ask for the missing required information naturally
        - Only proceed to completion when ALL required fields are filled
        - CRITICAL: Do NOT assume story is complete just because setup steps (characters, photos, setting) are done
        - The story content (problem, actions, outcome) must be collected before considering the story complete
        {auth_instructions}
        
        NEW STORY REQUESTS & USER INTENT:
        - NATURALLY detect when users want to create new stories (any variation of "I want another story", "new story", "start over", "different story")
        - Follow the authentication-specific instructions above based on user status
        
        CHARACTER CONNECTION SYNONYMS:
        - Accept multiple terms for writer/creator relationship: "writer", "creator", "author", "screenwriter", "storyteller", "I'm just the writer", "I'm only the creator"
        - Don't get confused by different terms - they all mean the same thing
        - Use the term the user prefers in your responses

        RESPONSE GUIDELINES:
        1. Keep responses SHORT (1-2 sentences max)
        2. Ask ONE focused question at a time
        3. Always acknowledge what they've shared
        4. Use character names, not pronouns
        5. Be warm and encouraging
        6. Follow the structured flow above

        EXAMPLES (Slot-based):
        ❌ BAD: "What's your story about? When does it take place?"
        ✅ GOOD: "Who is the main character of your story?" (Step 1 - FIRST question)

        ❌ BAD: "What does he do?" (when character name is John)
        ✅ GOOD: "What does John do to face this challenge?" (actions_taken)

        ❌ BAD: Asking "Who is the main character?" when user already said "Sarah"
        ✅ GOOD: "You mentioned Sarah earlier. What's the main problem Sarah faces?" (problem_statement)

        ❌ BAD: Continuing to ask questions after user says "at the end of the story..."
        ✅ GOOD: "That's a beautiful story about [character name]! What makes this story special to you?" (likes_in_story)

        SLOT-BASED ROUTING (Follow EXACT workflow order):
        STEP 1: If heroes array is empty → Ask "Who is the main character of your story?" (This is the FIRST question)
        STEP 2: If heroes array is empty or first hero incomplete → Collect hero: name → age_at_story → relationship_to_user → physical_descriptors → personality_traits
        - If first hero collected and second hero not asked → Ask "Is there a second hero in the story?"
        - If second hero needed → Collect full intake for hero #2
        STEP 3: If all heroes collected and supporting_characters not asked → Ask "Are there other important people in the story?" (up to 2, light metadata only)
        STEP 4: If all heroes and supporting characters collected → Check for photos:
        - CRITICAL: Before asking about photos, check if characters already have photo_url set in the dossier
        - Only ask about photos for characters that do NOT have a photo_url (or have empty photo_url)
        - For each hero WITHOUT photo_url: "Do you have a photo of [hero name]? You can upload it now or skip and we'll send you a link later."
        - For each supporting character WITHOUT photo_url (optional): "Do you have a photo of [character name]? (optional - you can skip)"
        - If a character already has a photo_url in the dossier, DO NOT ask about photos for that character again
        - Skip to next step if all characters already have photos (or user has skipped/declined)
        STEP 5: If all characters and photos done, and setting incomplete → Ask Setting & Time:
        - If story_location is Unknown → Ask "Where does the story happen?"
        - If story_timeframe is Unknown → Ask "What time period?"
        - If season_time_of_year is empty → Ask "Season/time of year?"
        - If environmental_details is empty → Ask "Any meaningful environmental details?"
        STEP 6: If story_type is Unknown or "other" → Ask "What type of story do you want? Please choose one:
          • Romantic
          • Childhood drama
          • Fantasy
          • Epic/legend
          • Adventure
          • Historic action
          • Documentary tone
          • Other"
          Wait for explicit choice and map to exact value.
        STEP 7: If audience.who_will_see_first is empty → Ask "Who will see this first?"
        - If audience.desired_feeling is empty → Ask "What do you want them to feel?" (CRITICAL: Must ask this after who_will_see_first)
        - If perspective is Unknown → Ask "What perspective?" (first_person, narrator_voice, legend_myth_tone, documentary_tone)
        STEP 8: STORY CONTENT COLLECTION (CRITICAL - Must collect story before asking about ending):
        - After all setup steps (characters, photos, setting, story type, audience) are complete, collect the ACTUAL STORY:
        - If problem_statement is Unknown or empty → Ask "What's the main problem or challenge [hero name] faces in this story?"
        - If actions_taken is Unknown or empty → Ask "What does [hero name] do to address this problem or navigate this situation?"
        - ONLY after problem_statement and actions_taken are collected, then ask about outcome
        - DO NOT ask about the ending until the story problem and actions have been collected
        STEP 9: OUTCOME (Only after story content is collected):
        - If outcome is Unknown or empty AND problem_statement and actions_taken are already collected → Ask "How does the story end? What's the final outcome or resolution?"
        - CRITICAL: Only ask about ending AFTER the story problem and actions have been discussed
        STEP 10: Data packaging happens automatically when all steps are complete

        ATTACHMENT ANALYSIS GUIDELINES:
        - When the user shares images or attachments, ALWAYS provide detailed visual analysis
        - Your analysis will be stored for future reference, so be thorough and specific
        - Focus on all relevant visual details: appearance, expression, setting, atmosphere, mood, composition
        - Consider the user's message as guidance - if they say "this is my character", analyze character details
        - If they say "this is where the story takes place", focus on location/setting details
        - Incorporate the visual details you observe naturally into your conversational response
        - Mention specific visual elements (e.g., "I can see [character name] has [description]")
        - Use conversation history to provide context-aware analysis (e.g., if character was mentioned before)
        - If MULTIPLE IMAGES are present, structure your reply strictly as:
          1) "Image 1: <filename>" — full analysis
          2) "Image 2: <filename>" — full analysis
          [...]
          3) "Combined Summary" — compare/contrast and connect to story slots (character, frame, or setting)

        CONVERSATION CONTEXT:
        {self._build_conversation_context(kwargs.get("conversation_history", []), kwargs.get("image_context", ""))}

        {revision_prompt}

        Be Ariel - warm, story-focused, and always building on what they share.{rag_context_text}{dossier_info}"""

            # Build messages with conversation history for context
            messages = [{"role": "system", "content": system_prompt}]
            
            # Add conversation history if provided
            history = kwargs.get("conversation_history", [])
            if history:
                # Limit to last 10 messages to avoid token limits
                recent_history = history[-10:]
                messages.extend(recent_history)
                print(f"📚 Using {len(recent_history)} messages from history for context")
            
            # Check if images are provided for direct sending (ChatGPT-style)
            image_data_list = kwargs.get("image_data", [])  # List of {"data": bytes, "mime_type": str, "filename": str}
            
            # Build user message content (ChatGPT-style content array)
            if image_data_list:
                # ChatGPT-style: Send images directly to model
                # Preface to enumerate images and require sectioned outputs
                filenames = [img.get("filename", "image.png") for img in image_data_list]
                if len(filenames) > 1:
                    listing = "\n".join([f"{i+1}) {name}" for i, name in enumerate(filenames)])
                    preface = (
                        "You will receive multiple images. Analyze each one in its own section and then add a Combined Summary.\n"
                        f"Images:\n{listing}\n"
                        "Format strictly: Image 1: <filename> … Image 2: <filename> … Combined Summary: …\n"
                    )
                else:
                    preface = ""
                user_content = [{"type": "text", "text": (preface + prompt) if preface else prompt}]
                
                for img_data in image_data_list:
                    image_bytes = img_data.get("data")
                    mime_type = img_data.get("mime_type", "image/png")
                    filename = img_data.get("filename", "image.png")
                    
                    if image_bytes:
                        import base64
                        base64_image = base64.b64encode(image_bytes).decode('utf-8')
                        user_content.append({
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_image}"
                            }
                        })
                        print(f"🖼️ [AI] Added image to message: {filename} ({len(image_bytes)} bytes, {mime_type})")
                
                messages.append({"role": "user", "content": user_content})
                print(f"✅ [AI] User message contains {len(image_data_list)} image(s) - using GPT-4o for vision")
            else:
                # Fallback: Use text description if provided (for backward compatibility)
                image_context = kwargs.get("image_context", "")
                if image_context:
                    user_message = f"{prompt}\n\n{image_context}"
                    print(f"🖼️ [AI] Using text description fallback ({len(image_context)} chars)")
                else:
                    user_message = prompt
                    print(f"ℹ️ [AI] No image data or context available")
                
                messages.append({"role": "user", "content": user_message})
            
            # Log message details
            print(f"📋 [AI] Total messages: {len(messages)}")
            if image_data_list:
                print(f"📋 [AI] User message has {len(image_data_list)} image(s) - will use GPT-4o")
            else:
                last_msg = messages[-1]
                if isinstance(last_msg.get("content"), list):
                    print(f"📋 [AI] User message is content array with {len(last_msg['content'])} items")
                else:
                    print(f"📋 [AI] User message length: {len(str(last_msg.get('content', '')))} chars")

            # Select model based on whether images are present
            # GPT-4o has vision capabilities, GPT-4o-mini is cheaper for text-only
            model_name = "gpt-4o" if image_data_list else "gpt-4o-mini"
            
            print(f"🤖 [AI] Selected model: {model_name} ({'vision-capable' if image_data_list else 'text-only'})")

            response = openai.chat.completions.create(
                model=model_name,  # Use GPT-4o for vision, GPT-4o-mini for text-only
                messages=messages,
                max_completion_tokens=kwargs.get("max_tokens", 600),  # Increased for multi-image, richer context
                temperature=0.7,
                top_p=1.0,  # Standard value for balanced creativity
                n=1,  # Single response
                stream=False,  # Non-streaming for API consistency
                presence_penalty=0.0,  # No penalty for topic repetition
                frequency_penalty=0.0  # No penalty for word repetition
            )
            
            print(f"✅ OpenAI response received: {response}")

            return {
                "response": response.choices[0].message.content,
                "model_used": model_name,
                "tokens_used": response.usage.total_tokens if response.usage else 0
            }
        except Exception as e:
            print(f"❌ OpenAI chat error: {str(e)}")
            print(f"❌ Error type: {type(e).__name__}")
            import traceback
            print(f"❌ Full traceback: {traceback.format_exc()}")
            raise Exception(f"OpenAI chat error: {str(e)}")
    
    async def _generate_description_response(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Generate description using Gemini 2.5 Flash with fallback to GPT"""
        try:
            # Check if this is a synopsis generation (prompt contains "synopsis" or "500-800 words")
            is_synopsis = "synopsis" in prompt.lower() or "500-800 words" in prompt.lower()
            
            # For synopsis, use the prompt directly without wrapping
            # For other descriptions, wrap it
            if is_synopsis:
                final_prompt = prompt
                max_tokens = kwargs.get("max_tokens", 3200)  # Higher for synopsis
                temperature = kwargs.get("temperature", 0.7)  # Use provided temperature
            else:
                final_prompt = f"Generate a detailed, vivid description for: {prompt}"
                max_tokens = kwargs.get("max_tokens", 2000)
                temperature = kwargs.get("temperature", 0.8)
            
            gemini_succeeded = False
            if self.gemini_available:
                # Use Gemini 2.5 Flash (best price-performance model)
                # Note: Using new google.genai package (migrated from deprecated google.generativeai)
                try:
                    print(f"📝 [AI] Generating with Gemini 2.5 Flash, max_output_tokens: {max_tokens}, is_synopsis: {is_synopsis}")
                    
                    # Use new google.genai API with proper types
                    # Reference: https://github.com/googleapis/python-genai
                    response = self.gemini_client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=final_prompt,
                        config=genai_types.GenerateContentConfig(
                            max_output_tokens=max_tokens,
                            temperature=temperature,
                        )
                    )
                    
                    # Get response text - new API returns text directly
                    response_text = response.text
                    
                    word_count = len(response_text.split())
                    print(f"📝 [AI] Gemini 2.5 Flash response: {word_count} words")
                    if word_count < 400 and is_synopsis:
                        print(f"⚠️ [AI] WARNING: Synopsis response is too short! May be truncated.")

                    # Try to get token count if available (new API structure)
                    tokens_used = 0
                    if hasattr(response, 'usage_metadata'):
                        usage = response.usage_metadata
                        if hasattr(usage, 'total_token_count'):
                            tokens_used = usage.total_token_count
                        elif hasattr(usage, 'prompt_token_count') and hasattr(usage, 'candidates_token_count'):
                            tokens_used = usage.prompt_token_count + usage.candidates_token_count

                    return {
                        "response": response_text,
                        "model_used": "gemini-2.5-flash",
                        "tokens_used": tokens_used
                    }
                except Exception as e:
                    print(f"⚠️ Gemini 2.5 Flash failed: {e}")
                    import traceback
                    print(f"⚠️ Traceback: {traceback.format_exc()}")
                    print(f"⚠️ Falling back to GPT for description generation")
                    # Mark that Gemini failed, fall through to GPT fallback
                    gemini_succeeded = False
            
            # Fallback to GPT if Gemini not available or failed
            if not self.gemini_available or not gemini_succeeded:
                # Use GPT-4.1 for synopsis, GPT-4o for other descriptions
                gpt_model = "gpt-4.1" if is_synopsis else "gpt-4o"
                
                if is_synopsis:
                    system_content = "You are a professional story synopsis writer. Write complete, comprehensive synopses that are 500-800 words long. Always complete your synopsis fully - never truncate or cut off mid-sentence."
                    user_content = final_prompt
                    max_tokens = kwargs.get("max_tokens", 3200)
                else:
                    system_content = "You are a creative writing assistant specializing in vivid, detailed descriptions. Generate engaging, sensory-rich descriptions that bring scenes to life."
                    user_content = f"Generate a detailed, vivid description for: {prompt}"
                    max_tokens = kwargs.get("max_tokens", 2000)
                
                print(f"📝 [AI] Generating with {gpt_model} (fallback), max_completion_tokens: {max_tokens}, is_synopsis: {is_synopsis}")
                response = openai.chat.completions.create(
                    model=gpt_model,
                    messages=[
                        {"role": "system", "content": system_content},
                        {"role": "user", "content": user_content}
                    ],
                    max_completion_tokens=max_tokens,
                    temperature=temperature,
                    top_p=1.0,
                    n=1,
                    stream=False,
                    presence_penalty=0.0,
                    frequency_penalty=0.0
                )
                
                response_text = response.choices[0].message.content
                word_count = len(response_text.split())
                print(f"📝 [AI] {gpt_model} response: {word_count} words, tokens: {response.usage.total_tokens if response.usage else 'unknown'}")

                return {
                    "response": response_text,
                    "model_used": gpt_model,
                    "tokens_used": response.usage.total_tokens if response.usage else 0
                }
        except Exception as e:
            raise Exception(f"Description generation error: {str(e)}")
    
    async def _generate_script_response(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Generate video tutorial script from captured story data"""
        try:
            # Get dossier context for script generation
            dossier_context = kwargs.get("dossier_context", {})
            
            # Build comprehensive script prompt
            script_prompt = f"""You are a professional video scriptwriter for Stories We Tell. Create a compelling 3-5 minute video tutorial script based on the captured story data.

STORY DATA:
Time: {dossier_context.get('story_timeframe', 'Not specified')}
Location: {dossier_context.get('story_location', 'Not specified')}
World Type: {dossier_context.get('story_world_type', 'Not specified')}
Character: {dossier_context.get('subject_full_name', 'Not specified')}
Relationship: {dossier_context.get('subject_relationship_to_writer', 'Not specified')}
Problem: {dossier_context.get('problem_statement', 'Not specified')}
Actions: {dossier_context.get('actions_taken', 'Not specified')}
Outcome: {dossier_context.get('outcome', 'Not specified')}
Why This Story: {dossier_context.get('likes_in_story', 'Not specified')}

SCRIPT REQUIREMENTS:
1. Create a 3-5 minute video tutorial script
2. Use a warm, personal tone
3. Include visual cues and pacing notes
4. Structure: Introduction → Story Setup → Character Journey → Resolution → Call to Action
5. Make it engaging and emotionally resonant
6. Include specific details from the story data above

FORMAT:
[VIDEO SCRIPT FORMAT]
[SCENE 1: Introduction]
[Visual: Warm, inviting setting]
[Narrator]: "Today, I want to share a story about..."

[Continue with full script structure]

Generate a complete, production-ready video script."""

            # Use Claude Sonnet 4.5 for script generation (SOTA for structured long-form writing)
            if self.claude_available:
                response = self.claude_client.messages.create(
                    model="claude-sonnet-4-5-20250929",  # Latest Claude Sonnet 4.5 model (per Anthropic API docs)
                    max_tokens=kwargs.get("max_tokens", 8000),  # Claude Sonnet 4.5 supports up to 64K tokens out
                    temperature=kwargs.get("temperature", 0.7),
                    messages=[
                        {"role": "user", "content": script_prompt}
                    ]
                )

                return {
                    "response": response.content[0].text,
                    "model_used": "claude-sonnet-4-5-20250929",
                    "tokens_used": response.usage.input_tokens + response.usage.output_tokens,
                    "script_type": "video_tutorial",
                    "estimated_duration": "3-5 minutes"
                }
            else:
                # Fallback to GPT-4.1 (flagship for deep text generation)
                response = openai.chat.completions.create(
                    model="gpt-4.1",
                    messages=[
                        {"role": "system", "content": "You are a professional video scriptwriter specializing in personal storytelling and documentary-style content. Create engaging, emotionally resonant scripts that bring stories to life."},
                        {"role": "user", "content": script_prompt}
                    ],
                    max_completion_tokens=kwargs.get("max_tokens", 4000),
                    temperature=0.7,
                    top_p=1.0,
                    n=1,
                    stream=False,
                    presence_penalty=0.0,
                    frequency_penalty=0.0
                )

                return {
                    "response": response.choices[0].message.content,
                    "model_used": "gpt-4.1",
                    "tokens_used": response.usage.total_tokens if response.usage else 0,
                    "script_type": "video_tutorial",
                    "estimated_duration": "3-5 minutes"
                }
        except Exception as e:
            raise Exception(f"Script generation error: {str(e)}")
    
    async def _generate_scene_response(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Generate scene using GPT-4.1 (flagship for deep text generation) or fallback to Claude Sonnet 4.5"""
        try:
            # Use GPT-4.1 for scene generation (flagship for deep text generation with 1M token context)
            response = openai.chat.completions.create(
                model="gpt-4.1",
                messages=[
                    {"role": "system", "content": "You are a professional screenwriter and scene director. Generate detailed, cinematic scenes with vivid descriptions, character actions, dialogue, and visual elements. Focus on creating immersive, emotionally engaging scenes with strong instruction-following and coherence over long passages."},
                    {"role": "user", "content": f"Generate a detailed, cinematic scene based on: {prompt}"}
                ],
                max_completion_tokens=kwargs.get("max_tokens", 3000),  # Increased for GPT-4.1
                temperature=kwargs.get("temperature", 0.8),  # Higher creativity for scenes
                top_p=1.0,
                n=1,
                stream=False,
                presence_penalty=0.0,
                frequency_penalty=0.0
            )

            return {
                "response": response.choices[0].message.content,
                "model_used": "gpt-4.1",
                "tokens_used": response.usage.total_tokens if response.usage else 0
            }
        except Exception as e:
            # Fallback to Claude Sonnet 4.5 if GPT-4o fails
            if self.claude_available:
                try:
                    response = self.claude_client.messages.create(
                        model="claude-sonnet-4-5-20250929",  # Latest Claude Sonnet 4.5 model (per Anthropic API docs)
                        max_tokens=kwargs.get("max_tokens", 3000),
                        temperature=kwargs.get("temperature", 0.8),
                        messages=[
                            {"role": "user", "content": f"Generate a detailed, cinematic scene based on: {prompt}"}
                        ]
                    )

                    return {
                        "response": response.content[0].text,
                        "model_used": "claude-sonnet-4-5-20250929",
                        "tokens_used": response.usage.input_tokens + response.usage.output_tokens
                    }
                except Exception as claude_error:
                    raise Exception(f"Both GPT-4.1 and Claude failed: GPT-4.1 error: {str(e)}, Claude error: {str(claude_error)}")
            else:
                raise Exception(f"GPT-4.1 scene generation error: {str(e)}")
    

# Global instance
ai_manager = AIModelManager()

