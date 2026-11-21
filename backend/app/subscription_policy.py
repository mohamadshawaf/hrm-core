"""Opt-in subscription access and employee-seat enforcement.

The default commercial trial is provisional. Enforcement remains disabled
unless explicitly configured by the deployment operator.
"""

import time


class SubscriptionInactive(Exception):
    pass


class EmployeeSeatLimit(Exception):
    pass


class SubscriptionPolicy:
    def __init__(self, connection):
        self.connection = connection

    def active_plan(self, organization_id: str):
        row = self.connection.execute(
            'SELECT s.status,s.period_ends_at,p.max_employees '
            'FROM organization_subscriptions s '
            'JOIN subscription_plans p ON p.id=s.plan_id '
            'WHERE s.organization_id=?',
            (organization_id,),
        ).fetchone()
        if (row is None or row['status'] not in ('trialing', 'active') or
                row['period_ends_at'] <= int(time.time())):
            raise SubscriptionInactive()
        return row

    def require_seat(self, organization_id: str):
        # Every employee insertion for an organization serializes on its
        # subscription row; PostgreSQL's row lock prevents concurrent overbooking.
        # SQLite serializes writers when the UPDATE occurs.
        self.connection.execute(
            'UPDATE organization_subscriptions SET version=version '
            'WHERE organization_id=?', (organization_id,),
        )
        plan = self.active_plan(organization_id)
        used = self.connection.execute(
            'SELECT COUNT(*) FROM employees '
            'WHERE organization_id=? AND archived_at IS NULL',
            (organization_id,),
        ).fetchone()[0]
        if used >= plan['max_employees']:
            raise EmployeeSeatLimit()
