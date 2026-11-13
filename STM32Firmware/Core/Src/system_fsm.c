#include "system_fsm.h"

static SystemState current_state = SYSTEM_INIT;

SystemState SystemFsm_GetState(void)
{
    return current_state;
}

bool SystemFsm_HandleEvent(SystemEvent event)
{
    /* Errors take precedence over normal state transitions. */
    if (event == SYSTEM_EVENT_ERROR)
    {
        current_state = SYSTEM_FAULT;
        return true;
    }

    if (event == SYSTEM_EVENT_STOP)
    {
        switch (current_state)
        {
            case SYSTEM_READY:
            case SYSTEM_RUNNING:
                current_state = SYSTEM_STOPPED;
                return true;

            case SYSTEM_STOPPED:
            case SYSTEM_FAULT:
                /* Repeated Stop is accepted without clearing a fault. */
                return true;

            default:
                return false;
        }
    }

    switch (current_state)
    {
        case SYSTEM_INIT:
            if (event == SYSTEM_EVENT_INIT_DONE)
            {
                current_state = SYSTEM_READY;
                return true;
            }
            break;

        case SYSTEM_READY:
            if (event == SYSTEM_EVENT_START)
            {
                current_state = SYSTEM_RUNNING;
                return true;
            }
            break;

        case SYSTEM_STOPPED:
        case SYSTEM_FAULT:
            if (event == SYSTEM_EVENT_RESET_ALLOWED)
            {
                current_state = SYSTEM_READY;
                return true;
            }
            break;

        case SYSTEM_RUNNING:
        default:
            break;
    }

    return false;
}
