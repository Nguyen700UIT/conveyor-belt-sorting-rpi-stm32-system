#ifndef SERVO_FSM_H
#define SERVO_FSM_H

#include <stdbool.h>
#include <stdint.h>

typedef enum
{
    SERVO_FSM_UNINITIALIZED = 0,
    SERVO_FSM_IDLE,
    SERVO_FSM_DEFLECTING,
    SERVO_FSM_HOLDING,
    SERVO_FSM_RETURNING
} ServoFsmState;

typedef struct
{
    int16_t rest_angle;
    int16_t deflect_angle;
    uint32_t deflect_ms;
    uint32_t hold_ms;
    uint32_t return_ms;
} ServoFsmConfig;

/* Apply angle requests immediately, then schedule the next deadline.
 * cycle_completed means timed motion completed, not confirmed physical sorting.
 * product_id is meaningful only when cycle_completed is true.
 */
typedef struct
{
    bool angle_requested;
    int16_t angle;
    bool cycle_completed;
    uint32_t product_id;
} ServoFsmOutput;

/* One zero-initialized instance per servo. Main-loop use only.
 * deadline_ms is valid only in DEFLECTING, HOLDING or RETURNING.
 * Treat fields as read-only outside this module.
 */
typedef struct
{
    ServoFsmState state;
    ServoFsmConfig config;
    uint32_t deadline_ms;
    uint32_t product_id;
    bool cycle_active;
} ServoFsm;

/* Initialize once at boot. Durations must be 1..INT32_MAX ms.
 * now_ms is a wrapping uint32_t millisecond clock shared with the scheduler.
 * Service deadlines less than 2^31 ms late; no periodic polling is required.
 * Output pointers are required; each call clears its output before processing.
 * A false return leaves the FSM unchanged and emits no action.
 */
bool ServoFsm_Init(ServoFsm *fsm, const ServoFsmConfig *config,
                   uint32_t now_ms, ServoFsmOutput *output);
bool ServoFsm_Start(ServoFsm *fsm, uint32_t product_id,
                    uint32_t now_ms, ServoFsmOutput *output);
bool ServoFsm_Stop(ServoFsm *fsm, uint32_t now_ms, ServoFsmOutput *output);
bool ServoFsm_HandleTimeout(ServoFsm *fsm, uint32_t now_ms,
                            ServoFsmOutput *output);

#endif /* SERVO_FSM_H */
