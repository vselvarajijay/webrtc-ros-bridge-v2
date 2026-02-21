# Interpreted navigation state from flow + velocity.
# -1 = turn LEFT, 0 = STRAIGHT, 1 = turn RIGHT

std_msgs/Header header

bool forward_safe
int8 safest_turn
float32 urgency_score
float32 confidence
