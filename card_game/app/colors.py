# ANSI Color Codes for terminal UI
class Colors:
    TURQUOISE = '\033[96m' 
    SKY_BLUE = '\033[94m'  
    ORANGE = '\033[33m'    
    GREY = '\033[90m'      
    
    # Aliases and standard colors
    CYAN = TURQUOISE
    BLUE = SKY_BLUE
    YELLOW = '\033[93m'
    GREEN = '\033[92m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    STRIKETHROUGH = '\033[9m'
    UNDERLINE = '\033[4m'
    RESET = '\033[0m'
    HEADER = '\033[95m'
    CLEAR = '\033[H\033[J'  # Home + Clear screen
