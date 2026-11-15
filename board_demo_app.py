"""Public, synthetic-only Platform Compass deployment."""
from __future__ import annotations
from rwit_deployment_guard import select_deployment, assert_mode

def main() -> None:
    select_deployment('demo')
    assert_mode('demo')
    # Import after binding the deployment; source readers must check demo first.
    from board_app import main as board_main
    board_main(cloud_mode=False)

if __name__ == '__main__':
    main()
