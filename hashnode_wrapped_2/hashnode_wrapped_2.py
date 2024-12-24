import reflex as rx
import httpx
from typing import Dict, Optional, List, Any
import os 
from dotenv import load_dotenv
from datetime import datetime
import urllib.parse

# Load environment variables from .env file
load_dotenv(override=True)

# Update the API URL to the correct GraphQL endpoint
HASHNODE_API_URL = "https://gql.hashnode.com"

# Debug print to check if environment variable is loaded
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")  # Changed to uppercase
if not ACCESS_TOKEN:
    print("Warning: ACCESS_TOKEN not found in environment variables")


# Update GraphQL query to match working format
USER_STATS_QUERY = """
query($username: String!) {
    user(username: $username) {
        username
        followersCount
        badges {
            name
        }
        posts(page: 1, pageSize: 20) {
            nodes {
                title
                publishedAt
                views
                reactionCount
                replyCount    
            }
        }
    }
}
"""

class State(rx.State):
    """The app state."""
    username: str = ""
    is_loading: bool = False
    error_message: Optional[str] = None
    user_data: Dict = {}  
    stats_items: List[Dict[str, str]] = []
    user_display_name: str = ""
    posts_2024: List[Dict] = []
    post_count: int = 0 

    def process_stats(self, user_data: Dict) -> None:
        """Process API data into displayable stats for 2024."""
        try:
            self.user_data = user_data
            
            # Filter posts for 2024
            all_posts = user_data.get("posts", {}).get("nodes", [])
            self.posts_2024 = [
                post for post in all_posts 
                if post.get("publishedAt") and 
                datetime.fromisoformat(post["publishedAt"].replace("Z", "+00:00")).year == 2024
            ]
            
            # Set post count
            self.post_count = len(self.posts_2024)
            
            total_views = sum(post.get("views", 0) for post in self.posts_2024)
            total_reactions = sum(post.get("reactionCount", 0) for post in self.posts_2024)
            total_followers = user_data.get("followersCount", 0)
            total_badges = len(user_data.get("badges", [])) if user_data.get("badges") else 0
            
            self.user_display_name = user_data.get("username", "")
            self.stats_items = [
                {"title": "Total Articles", "value": str(self.post_count), "description": "Articles published in 2024"},
                {"title": "Total Views", "value": f"{total_views:,}", "description": "Content views in 2024"},
                {"title": "Total Reactions", "value": str(total_reactions), "description": "Reactions in 2024"},
                {"title": "Followers", "value": str(total_followers), "description": "Total followers"},
                {"title": "Badges Earned", "value": str(total_badges), "description": "Total badges collected"},
                {"title": "Avg. Reactions", 
                 "value": f"{total_reactions/self.post_count:.1f}" if self.post_count > 0 else "0",
                 "description": "Average reactions per post"}
            ]
        except Exception as e:
            print(f"Error processing stats: {e}")
            self.stats_items = []
            self.post_count = 0

    async def handle_submit(self):
        """Handle the form submission."""
        if not self.username:
            self.error_message = "Please enter a username"
            return
        
        if not ACCESS_TOKEN:
            self.error_message = "Access token not configured. Please check your .env file contains ACCESS_TOKEN"
            return
        
        self.is_loading = True
        self.error_message = None
        
        try:
            headers = {
                "Authorization": ACCESS_TOKEN,  
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    HASHNODE_API_URL,
                    json={
                        "query": USER_STATS_QUERY,
                        "variables": {"username": self.username}
                    },
                    headers=headers,
                    timeout=30.0
                )
                
                # Add debug print
                print("Response status:", response.status_code)
                print("Response body:", response.text)
                
                # Check for HTTP errors first
                response.raise_for_status()
                
                data = response.json()
                
                # Check for GraphQL errors
                if "errors" in data:
                    error_message = data["errors"][0].get("message", "Unknown GraphQL error")
                    if "unauthorized" in error_message.lower() or "authentication" in error_message.lower():
                        self.error_message = "Invalid access token. Please check your configuration."
                    else:
                        self.error_message = f"API Error: {error_message}"
                    return
                
                if not data.get("data", {}).get("user"):
                    self.error_message = "User not found"
                    return
                
                self.process_stats(data["data"]["user"])
                return rx.redirect("/stats")
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                self.error_message = "Invalid access token. Please check your configuration."
            elif e.response.status_code == 403:
                self.error_message = "Access forbidden. Please check your permissions."
            else:
                self.error_message = f"HTTP Error: {str(e)}"
        except httpx.RequestError as e:
            self.error_message = f"Network Error: {str(e)}"
        except Exception as e:
            self.error_message = f"An unexpected error occurred: {str(e)}"
        finally:
            self.is_loading = False

    def share_stats(self) -> None:
        """Share stats to Twitter."""
        stats_summary = []
        for stat in self.stats_items:
            if stat["title"] in ["Total Articles", "Total Views", "Total Reactions"]:
                stats_summary.append(f"{stat['title']}: {stat['value']}")
        
        stats_text = " | ".join(stats_summary)
        tweet_text = f"Check out my @hashnode Wrapped 2024!\n\n{stats_text}\n\nGenerate yours at https://hashnode_wrapped_2-gold-panda.reflex.run by @sophiairoegbu_\n\n#HashnodeWrapped"
        
        # URL encode the tweet text
        encoded_text = urllib.parse.quote(tweet_text)
        share_url = f"https://twitter.com/intent/tweet?text={encoded_text}"
        
        return rx.redirect(share_url)

def color_mode_button():
    """Button to toggle color mode."""
    return rx.button(
        rx.icon("moon"),
        on_click=rx.toggle_color_mode,
        position="fixed",
        top="1rem",
        bg="transparent",
        border_color=rx.color_mode_cond("gray.200", "gray.600"),
    )


def index() -> rx.Component:
    """Main page of the application."""
    return rx.box(
        color_mode_button(),
        rx.center(
            rx.vstack(
                rx.heading(
                    "Your Hashnode Wrapped",
                    font_size=["1.8em", "2.5em", "5em"],  # Smaller font on mobile
                    padding_x=["4", "6", "8"],  # More padding control
                    text_align="center",
                    width=["100%", "100%", "auto"],  # Full width on mobile
                ),
                rx.heading(
                    "Review 2024",
                    font_size=["1.8em", "2.5em", "3em"],  # Responsive font sizes
                    background_image="linear-gradient(135deg, #2962FF 0%, #2962FF 100%)",
                    background_clip="text",
                    color="transparent",
                    font_weight="700",
                    text_align="center",
                    margin_bottom=["4", "6", "8"],  # Responsive margins
                ),
                rx.center(  # Added center wrapper
                    rx.form(
                        rx.vstack(
                            rx.input(
                                placeholder="Enter your Hashnode username",
                                on_change=State.set_username,
                                width="100%",
                                height="50px",
                                font_size="1.1em",
                                text_align="center",
                                border="2px solid",
                                border_color=rx.color_mode_cond("gray.300", "gray.600"),
                                border_radius="lg",
                                is_disabled=State.is_loading,
                                aria_label="Hashnode username input",  # Added ARIA label
                                _focus={
                                    "border_color": "#2962FF",
                                    "box_shadow": "0 0 0 1px #2962FF",
                                },
                            ),
                            rx.button(
                                "Generate your wrapped",
                                type_="submit",
                                on_click=State.handle_submit,
                                width="100%",
                                height="50px",
                                background_image="linear-gradient(135deg, #2962FF 0%, #2962FF 100%)",
                                color="white",
                                font_size="1.1em",
                                font_weight="bold",
                                border_radius="lg",
                                _hover={"opacity": 0.9},
                                is_disabled=State.is_loading,
                            ),
                            rx.cond(
                                State.is_loading,
                                rx.progress(
                                    is_indeterminate=True,
                                    color="#2962FF",
                                    width="100%",
                                ),
                            ),
                            rx.cond(
                                State.error_message,
                                rx.text(
                                    State.error_message,
                                    color="red.500",
                                    font_size="sm",
                                ),
                            ),
                            spacing="4",  # Fixed spacing value
                            width=["90%", "400px", "400px"],  # Adjusted width for mobile
                            max_width="90vw",  # Prevent overflow
                            align_items="center",
                            justify_content="center",  # Added justify_content
                        ),
                        width="100%",  # Added width to form
                        display="flex",  # Added display flex
                        justify_content="center",  # Added justify_content to form
                    ),
                    width="100%",  # Added width to center wrapper
                ),
                rx.box(
                    rx.text(
                        "Discover your blogging journey with Hashnode Wrapped:",
                        font_weight="bold",
                        margin_bottom="2",
                        color=rx.color_mode_cond("gray.700", "gray.300"),
                        text_align="center",
                    ),
                    rx.unordered_list(
                        rx.list_item("Your total article count and views in 2024"),
                        rx.list_item("Your writing consistency"),
                        rx.list_item("Reader engagement and reactions analysis"),
                        rx.list_item("Your follower growth and badges earned"),
                        color=rx.color_mode_cond("gray.600", "gray.400"),
                        padding_left="6",
                        spacing="2",
                    ),
                    margin_top="8",
                    width=["90%", "400px", "400px"],  # Adjusted width for mobile
                    max_width="90vw",
                ),
                spacing="6",  # Fixed spacing value
                padding=["4", "6", "8"],  # Adjusted padding for mobile
                align_items="center",
            ),
            bg=rx.color_mode_cond(
                "radial-gradient(circle at center, white 0%, #f0f0f0 100%)",
                "radial-gradient(circle at center, gray.800 0%, gray.900 100%)"
            ),
            min_height="100vh",
            width="100%",
        ),
    )


def stat_card(title: str, value: str, description: str) -> rx.Component:
    """Reusable card component for a single stat."""
    return rx.box(
        rx.vstack(
            rx.text(
                title.upper(),
                font_size=["sm", "md"],  # Responsive font size
                color=rx.color_mode_cond("gray.700", "gray.300"),  # Improved contrast
                font_weight="medium",
                aria_label=f"Statistic category: {title}",  # Added ARIA label
            ),
            rx.heading(
                value,
                size="1",
                color="#2962FF",  # Darker blue for better contrast
                font_weight="900",
                margin_y="2",
                font_size=["2em", "3em"],  # Responsive font size
                aria_label=f"Value: {value}",  # Added ARIA label
            ),
            rx.text(
                description,
                color=rx.color_mode_cond("gray.700", "gray.300"),  # Improved contrast
                font_size="sm",
                text_align="center",
            ),
            height=["150px", "180px", "220px"],  # Smaller on mobile
            width=["150px", "180px", "220px"],   # Smaller on mobile
            align_items="center",
            justify_content="center",
            spacing="4",
            role="article",  
        ),
        padding=["4", "6", "8"],  # Adjusted padding
        border="2px solid",
        border_color=rx.color_mode_cond("gray.300", "gray.600"),  # Improved contrast
        border_radius="2xl",
        background=rx.color_mode_cond(
            "rgba(255,255,255,0.98)", 
            "rgba(23,25,35,0.98)"
        ),
        backdrop_filter="blur(10px)",
        transition="all 0.3s",
        _hover={
            "transform": "translateY(-5px)",
            "box_shadow": "lg",
        },
        tab_index="0",  # Make focusable
        _focus={
            "outline": "2px solid",
            "outline_color": "#2962FF",
            "outline_offset": "2px",
        },
        aspect_ratio="1",
    )


def stats_page() -> rx.Component:
    return rx.box(
        color_mode_button(),
        rx.center(
            rx.vstack(
                rx.heading(
                    "Your 2024 Wrapped",
                    font_size=["1.8em", "2.5em", "5em"],
                    color=rx.color_mode_cond("#2962FF", "white"),
                    font_weight="900",
                    text_align="center",
                    margin_bottom=["4", "6", "8"],
                    padding_x="4",
                    line_height=["1.2", "1.3", "1.4"],
                ),
                rx.link(
                    "Skip to stats",
                    href="#stats-section",
                    position="absolute",
                    top="-40px",
                    left="50%",
                    transform="translateX(-50%)",
                    background="white",
                    padding="2",
                    z_index="999",
                    _focus={"top": "0"},
                ),
                rx.cond(
                    State.is_loading,
                    rx.text(
                        "Loading your stats...",
                        aria_live="polite",
                        position="absolute",
                        left="-9999px",
                    ),
                ),
                rx.cond(
                    State.user_data,
                    rx.vstack(
                        rx.vstack(
                            rx.heading(
                                f"@{State.user_display_name}'s Stats",
                                font_size=["1.2em", "1.5em", "2em"],
                                background_image="linear-gradient(135deg,rgb(18, 171, 205) 0%, #2962FF 100%)",
                                background_clip="text",
                                color="transparent",
                                font_weight="700",
                                text_align="center",
                                margin_y=["6", "8", "8"],
                                padding_x="4",
                                line_height=["1.2", "1.3", "1.4"],
                            ),
                            rx.text(
                                "You were awesome this year!",
                                color=rx.color_mode_cond("gray.600", "gray.400"),
                                font_size="lg",
                                margin_bottom="8",
                                text_align="center",
                            ),
                            width="100%",
                            align_items="center",
                            justify_content="center",
                            spacing="4",
                        ),
                        rx.hstack(
                            rx.foreach(
                                State.stats_items,
                                lambda item: stat_card(
                                    title=item["title"],
                                    value=item["value"],
                                    description=item["description"]
                                )
                            ),
                            spacing="4",
                            justify="center",
                            padding_x=["2", "4", "4"],
                            max_width="100vw",
                            margin_y=["4", "6", "8"],
                            flex_wrap="wrap",
                            overflow_x="hidden",
                        ),
                        width="100%",
                        padding_y=["4", "6", "8"],
                        spacing="6",
                    ),
                    rx.vstack(
                        rx.spinner(color="#00b4db", size="2"),
                        rx.text("Loading stats...", color="gray.500"),
                        spacing="4",
                    ),
                ),
                rx.hstack(
                    rx.button(
                        "Share My Wrapped",
                        on_click=State.share_stats,
                        background_image="linear-gradient(135deg, #2962FF 0%, #2962FF 100%)",
                        color="white",
                        height="50px",
                        width=["90%", "200px", "200px"],
                        font_size="1.1em",
                        font_weight="bold",
                        border_radius="lg",
                        _hover={"opacity": 0.9},
                    ),
                    rx.button(
                        "Check Another User",
                        on_click=lambda: rx.redirect("/"),
                        background_image="linear-gradient(135deg, #2962FF 0%, #2962FF 100%)",
                        color="white",
                        height="50px",
                        width=["90%", "200px", "200px"],
                        font_size="1.1em",
                        font_weight="bold",
                        border_radius="lg",
                        _hover={"opacity": 0.9},
                    ),
                    flex_direction=["column", "row", "row"],
                    spacing="4",
                    width=["90%", "auto", "auto"],
                    padding_top="8",
                ),
                spacing="6",
                padding=["4", "6", "8"],
                align_items="center",
                width="100%",
            ),
            bg=rx.color_mode_cond(
                "radial-gradient(circle at center, white 0%, #f0f0f0 100%)",
                "radial-gradient(circle at center, gray.800 0%, gray.900 100%)"
            ),
            min_height="100vh",
            width="100%",
            padding=["2", "4", "8"],
        ),
    )

# Update the app configuration at the bottom of the file
app = rx.App(
    style={
        "::selection": {
            "background_color": "#2962FF",
            "color": "white",
        },
        ":focus": {
            "outline": "2px solid #2962FF",
            "outline_offset": "2px",
        },
        "@media (max-width: 768px)": {
            "html": {
                "font_size": "14px",
            },
        },
        "@media (max-width: 480px)": {
            "html": {
                "font_size": "12px",
            },
            ".chakra-stack": {
                "width": "100%",
            },
        },
    },
    theme=rx.theme(
        has_background=True,
        include_toast=True,  
    ),
)

# Add pages with their routes
app.add_page(index, route="/")
app.add_page(stats_page, route="/stats")

backend_app = app
