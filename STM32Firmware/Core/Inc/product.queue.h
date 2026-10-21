#ifndef PRODUCT_QUEUE_H
#define PRODUCT_QUEUE_H

#include <stdbool.h>
#include <stdint.h>
#define QUEUE_CAP 16U


typedef enum
{
    PRODUCT_UNRIPE,
    PRODUCT_RIPE,
    PRODUCT_SPOILED
} ProductType;

bool ProductQueue_Push(ProductType product);
bool ProductQueue_Pop(ProductType *product);
uint8_t ProductQueue_Count(void);

#endif /* PRODUCT_QUEUE_H */
