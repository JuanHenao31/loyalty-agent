"""All loyalty agent tools, collected for the runtime."""

from app.agent.tools.add_points import add_points
from app.agent.tools.create_customer_with_card import create_customer_with_card
from app.agent.tools.explain_loyalty_policy import explain_loyalty_policy
from app.agent.tools.find_customer import find_customer
from app.agent.tools.get_company_analytics import get_company_analytics
from app.agent.tools.get_customer_history import get_customer_history
from app.agent.tools.get_customer_loyalty_status import get_customer_loyalty_status
from app.agent.tools.get_customer_rewards import get_customer_rewards
from app.agent.tools.redeem_reward import redeem_reward
from app.agent.tools.revoke_card import revoke_card

ALL_TOOLS = [
    find_customer,
    get_customer_loyalty_status,
    get_customer_rewards,
    get_customer_history,
    get_company_analytics,
    explain_loyalty_policy,
    create_customer_with_card,
    add_points,
    redeem_reward,
    revoke_card,
]
