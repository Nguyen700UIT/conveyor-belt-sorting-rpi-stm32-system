#ifndef SYSTEM_FSM_H
#define SYSTEM_FSM_H

#include <stdbool.h>

typedef enum
{
    SYSTEM_INIT = 0,
    SYSTEM_READY,
    SYSTEM_RUNNING,
    SYSTEM_STOPPED,
    SYSTEM_FAULT
} SystemState;

typedef enum
{
    SYSTEM_EVENT_INIT_DONE = 0,
    SYSTEM_EVENT_START,
    SYSTEM_EVENT_STOP,
    SYSTEM_EVENT_ERROR,
    SYSTEM_EVENT_RESET_ALLOWED,
    SYSTEM_EVENT_RESET_DENIED
} SystemEvent;

/* Call from the main loop only; this module does not control hardware. */
SystemState SystemFsm_GetState(void);

/* Returns true when accepted, including repeated Stop/Error.
 * RESET_ALLOWED must only be submitted after checking reset conditions.
 * ERROR must be dispatched before normal events pending in the same batch.
 */
bool SystemFsm_HandleEvent(SystemEvent event);

#endif /* SYSTEM_FSM_H */
