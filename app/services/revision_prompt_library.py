"""
Revision Prompt Library

Pre-written, effective prompts for common revision scenarios.
These prompts are automatically selected based on checklist items
that are unchecked during admin review.
"""

from typing import Dict, List, Optional

# Mapping of checklist keys to their corresponding prompts
REVISION_PROMPTS: Dict[str, Dict[str, str]] = {
    "character_logic": {
        "title": "Character Logic Review",
        "prompt": """The character details need clarification. Please review the character information 
and help ensure consistency. Ask the user to confirm or clarify character details, especially:
- Character names and relationships
- Ages and timelines
- Physical descriptions
- Personality traits

Ask naturally: I want to make sure I have all the character details correct. Can you help me 
clarify [specific character name]'s [specific detail that needs clarification]?"""
    },
    
    "photos": {
        "title": "Missing Character Photos",
        "prompt": """The story is missing photos for one or more characters. Photos help us create 
accurate visual representations of the characters in the video.

Ask the user: Do you have photos of [character name(s)] that you can share? You can upload them 
now, or we can send you a link to upload them later. Photos help us bring your characters to life 
visually in the story."""
    },
    
    "timeline": {
        "title": "Timeline Inconsistency",
        "prompt": """The story timeline needs clarification. There may be inconsistencies in the 
time period, dates, or sequence of events.

Ask the user: I want to make sure I understand the timeline correctly. Can you help clarify when 
this story takes place? Is it a specific year, time period, or present day? Also, are there any 
important dates or time sequences I should know about?"""
    },
    
    "setting": {
        "title": "Incomplete Setting Details",
        "prompt": """The story setting details are incomplete. We need more information about where 
and when the story takes place.

Ask the user: You mentioned the story takes place in [location if mentioned, otherwise skip this part]. 
Can you tell me more about the specific location? Is it a city, small town, rural area, or somewhere 
else? Also, what time period does the story happen - is it present day, a specific year, or a 
historical period? And what season or time of year is it?"""
    },
    
    "tone": {
        "title": "Story Type/Tone Mismatch",
        "prompt": """The story type or tone needs clarification. The narrative style should match 
the story type selected.

Ask the user: To make sure we capture the right tone for your story, can you help me understand 
the style you're looking for? Based on what you've shared, this sounds like a [suggested type] 
story. Does that feel right, or would you prefer a different style? The tone affects how we tell 
your story visually."""
    },
    
    "perspective": {
        "title": "Missing Audience & Perspective",
        "prompt": """The audience and perspective information is incomplete. We need to know who 
will see this story first and what feeling you want them to experience.

Ask the user: I'd like to understand who this story is for. Who will see this story first? And 
when they watch it, what do you want them to feel? Also, what perspective would work best - 
first person (as if they're experiencing it), narrator voice (someone telling the story), or 
another style?"""
    }
}

# Additional prompts for specific combinations
COMBINATION_PROMPTS: Dict[str, Dict[str, str]] = {
    "photos_and_setting": {
        "title": "Missing Photos and Setting",
        "prompt": """Two important pieces are missing: character photos and setting details.

First, ask about photos: Do you have photos of [character name(s)] that you can share? Photos 
help us create accurate visual representations.

Then, ask about setting: Also, can you tell me more about where and when this story takes place? 
What's the specific location, time period, and season?"""
    },
    
    "character_and_timeline": {
        "title": "Character and Timeline Issues",
        "prompt": """There are some inconsistencies in character details and timeline that need 
clarification.

Ask: I want to make sure I have everything correct. Can you help clarify [character name]'s age 
and the timeline? When exactly does this story take place, and how old was [character name] at 
that time?"""
    }
}

# Issue-specific prompts (for flagged issues)
ISSUE_PROMPTS: Dict[str, Dict[str, str]] = {
    "missing_info": {
        "title": "Missing Information",
        "prompt": """Some important information is missing from the story. Please ask the user 
to provide the missing details naturally, based on what specific information is missing."""
    },
    
    "conflicts": {
        "title": "Conflicting Information",
        "prompt": """There are some conflicting details in the story that need clarification. 
Please ask the user to help resolve these inconsistencies, being specific about what conflicts 
need to be addressed."""
    },
    
    "factual_gaps": {
        "title": "Factual Gaps",
        "prompt": """There are some gaps in the factual details of the story. Please ask the 
user to fill in these gaps, being specific about what information is needed."""
    }
}


def get_revision_prompt(
    unchecked_items: List[str],
    flagged_issues: Optional[Dict[str, List[str]]] = None
) -> str:
    """
    Generate a combined revision prompt based on unchecked checklist items.
    
    Args:
        unchecked_items: List of checklist keys that are unchecked (e.g., ["photos", "setting"])
        flagged_issues: Optional dict of flagged issues (e.g., {"missing_info": ["Hero photos"], "conflicts": []})
    
    Returns:
        Combined prompt string to inject into chat LLM system prompt
    """
    if not unchecked_items and not flagged_issues:
        return ""
    
    prompt_parts = []
    
    # Check for combination prompts first (more specific)
    if "photos" in unchecked_items and "setting" in unchecked_items:
        prompt_parts.append(COMBINATION_PROMPTS["photos_and_setting"]["prompt"])
        unchecked_items = [item for item in unchecked_items if item not in ["photos", "setting"]]
    
    if "character_logic" in unchecked_items and "timeline" in unchecked_items:
        prompt_parts.append(COMBINATION_PROMPTS["character_and_timeline"]["prompt"])
        unchecked_items = [item for item in unchecked_items if item not in ["character_logic", "timeline"]]
    
    # Add individual prompts for remaining unchecked items
    for item in unchecked_items:
        if item in REVISION_PROMPTS:
            prompt_parts.append(REVISION_PROMPTS[item]["prompt"])
    
    # Add issue-specific prompts if flagged
    if flagged_issues:
        for issue_type, issue_list in flagged_issues.items():
            if issue_list and issue_type in ISSUE_PROMPTS:
                issue_prompt = ISSUE_PROMPTS[issue_type]["prompt"]
                # Customize with specific issues
                if issue_list:
                    specific_issues = ", ".join(issue_list[:3])  # Limit to 3 for brevity
                    issue_prompt += f"\n\nSpecific issues to address: {specific_issues}"
                prompt_parts.append(issue_prompt)
    
    if not prompt_parts:
        return ""
    
    # Combine all prompts
    combined_prompt = "\n\n".join(prompt_parts)
    
    # Wrap in revision mode instructions
    full_prompt = f"""REVISION MODE ACTIVE:

The following items need attention:
{combined_prompt}

PRIORITY: Address the items mentioned above BEFORE continuing with other topics. 
Ask about these missing or unclear details in a natural, conversational way. 
Once all revision items are addressed, you can proceed normally with the conversation."""
    
    return full_prompt


def get_prompt_for_item(item_key: str) -> Optional[str]:
    """
    Get a specific prompt for a single checklist item.
    
    Args:
        item_key: Checklist item key (e.g., "photos", "setting")
    
    Returns:
        Prompt string or None if not found
    """
    if item_key in REVISION_PROMPTS:
        return REVISION_PROMPTS[item_key]["prompt"]
    return None


def get_all_prompt_titles() -> Dict[str, str]:
    """
    Get all available prompt titles for reference.
    
    Returns:
        Dict mapping item keys to their titles
    """
    titles = {}
    for key, data in REVISION_PROMPTS.items():
        titles[key] = data["title"]
    return titles


def get_user_friendly_question(
    unchecked_items: List[str],
    flagged_issues: Optional[Dict[str, List[str]]] = None
) -> str:
    """
    Generate a user-friendly question from revision prompts that can be shown directly to the user.
    This extracts the actual question part from the prompts.
    
    Args:
        unchecked_items: List of checklist keys that are unchecked
        flagged_issues: Optional dict of flagged issues
    
    Returns:
        User-friendly question string to display immediately when chat is reopened
    """
    if not unchecked_items and not flagged_issues:
        return "I need to gather some additional information to complete your story. Let's continue!"
    
    question_parts = []
    
    # Check for combination prompts first
    if "photos" in unchecked_items and "setting" in unchecked_items:
        question_parts.append("I need a couple of things to help complete your story. First, do you have photos of your characters that you can share? Photos help us create accurate visual representations. Also, can you tell me more about where and when this story takes place? What's the specific location, time period, and season?")
        unchecked_items = [item for item in unchecked_items if item not in ["photos", "setting"]]
    elif "photos" in unchecked_items:
        question_parts.append("Do you have photos of your characters that you can share? Photos help us create accurate visual representations of the characters in the video. You can upload them now, or we can send you a link to upload them later.")
        unchecked_items = [item for item in unchecked_items if item != "photos"]
    elif "setting" in unchecked_items:
        question_parts.append("Can you tell me more about where and when this story takes place? What's the specific location, time period, and season?")
        unchecked_items = [item for item in unchecked_items if item != "setting"]
    
    # Add individual prompts for remaining unchecked items
    for item in unchecked_items:
        if item == "character_logic":
            question_parts.append("I want to make sure I have all the character details correct. Can you help me clarify the character names, relationships, ages, and any other important character information?")
        elif item == "timeline":
            question_parts.append("I want to make sure I understand the timeline correctly. Can you help clarify when this story takes place? Is it a specific year, time period, or present day?")
        elif item == "tone":
            question_parts.append("To make sure we capture the right tone for your story, can you help me understand the style you're looking for? The tone affects how we tell your story visually.")
        elif item == "perspective":
            question_parts.append("I'd like to understand who this story is for. Who will see this story first? And when they watch it, what do you want them to feel? Also, what perspective would work best - first person, narrator voice, or another style?")
    
    # Add issue-specific questions
    if flagged_issues:
        for issue_type, issue_list in flagged_issues.items():
            if issue_list and len(issue_list) > 0:
                if issue_type == "missing_info":
                    specific_issues = ", ".join(issue_list[:3])
                    question_parts.append(f"I need some additional information: {specific_issues}. Can you help me fill in these details?")
                elif issue_type == "conflicts":
                    question_parts.append("I noticed some conflicting details in the story. Can you help me clarify these inconsistencies?")
                elif issue_type == "factual_gaps":
                    question_parts.append("There are some gaps in the factual details of the story. Can you help me fill in these gaps?")
    
    if not question_parts:
        return "I need to gather some additional information to complete your story. Let's continue!"
    
    # Combine questions naturally
    if len(question_parts) == 1:
        return question_parts[0]
    else:
        return "I need to gather a few more details to complete your story:\n\n" + "\n\n".join(f"{i+1}. {q}" for i, q in enumerate(question_parts))


async def get_active_revision_prompt(project_id: str) -> str:
    """
    Get the active revision prompt for a project by checking for active revision requests.
    
    Args:
        project_id: The project ID to check for active revisions
    
    Returns:
        Revision prompt string if active revision exists, empty string otherwise
    """
    try:
        from ..database.supabase import get_supabase_client
        
        supabase = get_supabase_client()
        
        # Check for active revision request for this project
        # First, get validation_id from validation_queue for this project
        validation_result = supabase.table("validation_queue")\
            .select("validation_id, review_checklist, review_issues, needs_revision")\
            .eq("project_id", project_id)\
            .eq("needs_revision", True)\
            .order("created_at", desc=True)\
            .limit(1)\
            .execute()
        
        if not validation_result.data:
            return ""
        
        validation = validation_result.data[0]
        review_checklist = validation.get("review_checklist", {})
        review_issues = validation.get("review_issues", {})
        
        # Get unchecked items from checklist
        unchecked_items = [
            key for key, checked in review_checklist.items() 
            if isinstance(checked, bool) and not checked
        ]
        
        # Get flagged issues
        flagged_issues = {}
        if review_issues:
            for issue_type in ["missing_info", "conflicts", "factual_gaps"]:
                issues = review_issues.get(issue_type, [])
                if issues and len(issues) > 0:
                    flagged_issues[issue_type] = issues
        
        # Generate revision prompt
        if unchecked_items or flagged_issues:
            return get_revision_prompt(unchecked_items, flagged_issues if flagged_issues else None)
        
        return ""
        
    except Exception as e:
        print(f"⚠️ [REVISION] Error getting active revision prompt: {e}")
        import traceback
        print(f"⚠️ [REVISION] Traceback: {traceback.format_exc()}")
        return ""

