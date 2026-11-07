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

typedef struct 
{
    uint32_t product_id;
    ProductType type;
    uint32_t deadline_ms;
} Product;

bool ProductQueue_Push(Product product);
bool ProductQueue_Pop(Product *product);
bool ProductQueue_PeekEarliest(Product* product);
bool ProductQueue_PopEarliest(Product* product);
uint8_t ProductQueue_Count(void);

#endif /* PRODUCT_QUEUE_H */
