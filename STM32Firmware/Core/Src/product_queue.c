#include "product.queue.h" 
#include <stddef.h>

static ProductType items_queue[QUEUE_CAP];

static uint8_t head;
static uint8_t tail;
static uint8_t count;

bool ProductQueue_Push(ProductType product)
{
    if (product != PRODUCT_UNRIPE && product != PRODUCT_RIPE && product != PRODUCT_SPOILED) return false;

    if (count >= QUEUE_CAP) return false;

    items_queue[tail] = product;
    tail = (uint8_t)((tail + 1) % (QUEUE_CAP));
    count++;
    
    return true;
}

bool ProductQueue_Pop(ProductType *product)
{
    if (product == NULL || count == 0U) return false;

    *product = items[head];
    head = uint8_t((head + 1U) % QUEUE_CAP);
    count--;
    
    return true;
}

uint8_t ProductQueue_Count(void)
{
    return count;
}