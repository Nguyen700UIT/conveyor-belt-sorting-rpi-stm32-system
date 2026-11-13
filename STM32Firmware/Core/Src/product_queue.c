#include "product_queue.h" 
#include <stddef.h>

static Product items_queue[QUEUE_CAP];

static uint8_t head;
static uint8_t tail;
static uint8_t count;

/* All queued deadlines must fit within a time span shorter than 2^31 ms.
 * Equal deadlines retain FIFO order. No queue state is changed.
 */
static bool FindEarliestIndex(uint8_t *index)
{
    if (index == NULL || count == 0U) return false;
    uint8_t earliest_idx = head;
    
    for (uint8_t i = 1U; i < count; i++)
    {
        const uint8_t idx = (uint8_t)((head + i) % QUEUE_CAP);
        const uint32_t delta = items_queue[idx].deadline_ms
                             - items_queue[earliest_idx].deadline_ms;
        if (delta > INT32_MAX)
        {
            earliest_idx = idx;
        }
    }

    *index = earliest_idx;
    return true;
}

bool ProductQueue_PeekEarliest(Product* productcpy)
{
    if (productcpy == NULL) return false;
    uint8_t index;
    bool found = FindEarliestIndex(&index);
    
    if (!found) return false;
    else *productcpy = items_queue[index];
    
    return true;
}

bool ProductQueue_PopEarliest(Product* productcpy)
{
    if (productcpy == NULL) return false;
    uint8_t index;
    bool found = FindEarliestIndex(&index);
    
    if (!found) return false;
    else *productcpy = items_queue[index];

    uint8_t next = (uint8_t)((index + 1U) % QUEUE_CAP);
    while (next != tail)
    {
        items_queue[index] = items_queue[next];
        index = next;
        next = (uint8_t)((index + 1U) % QUEUE_CAP);
    }
    count--;
    tail = index;
    return true;
}


bool ProductQueue_Push(Product product)
{
    if (product.type != PRODUCT_UNRIPE && product.type != PRODUCT_RIPE && product.type != PRODUCT_SPOILED) return false;

    if (count >= QUEUE_CAP) return false;

    items_queue[tail] = product;
    tail = (uint8_t)((tail + 1) % (QUEUE_CAP));
    count++;
    
    return true;
}

bool ProductQueue_Pop(Product *product)
{
    if (product == NULL || count == 0U) return false;

    *product = items_queue[head];
    head = (uint8_t)((head + 1U) % QUEUE_CAP);
    count--;
    
    return true;
}

uint8_t ProductQueue_Count(void)
{
    return count; 
}
