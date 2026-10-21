#ifndef SERVO_H
#define SERVO_H

#include "stm32f1xx_hal.h"

#define MIN_COUNTS 1000U
#define MAX_COUNTS 2000U

/* Requires a 1 MHz timer counter and a 20 ms PWM period.
 * angle: 0..180 degrees; 90 is the middle position (1500 us).
 * Start PWM separately with HAL_TIM_PWM_Start().
 */
void Set_Servo_Angle(TIM_HandleTypeDef* htim, uint32_t channel, int16_t angle);

/* Moves in 5 us pulse-width steps, one PWM frame (20 ms) apart. */
void Move_Servo_Angle_Smooth(TIM_HandleTypeDef* htim, uint32_t channel, int16_t angle);

#endif /* SERVO_H */
