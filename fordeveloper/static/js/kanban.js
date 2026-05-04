// ─── Kanban Drag & Drop ─────────────────────────────────
let draggedCard = null;

document.addEventListener('DOMContentLoaded', function() {
    const cards = document.querySelectorAll('.kanban-card');
    const columns = document.querySelectorAll('.kanban-cards');

    cards.forEach(card => {
        card.addEventListener('dragstart', function(e) {
            draggedCard = this;
            this.classList.add('dragging');
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/plain', this.dataset.id);
        });

        card.addEventListener('dragend', function() {
            this.classList.remove('dragging');
            document.querySelectorAll('.kanban-drop-target').forEach(el => {
                el.classList.remove('kanban-drop-target');
            });
            draggedCard = null;
        });
    });

    columns.forEach(column => {
        column.addEventListener('dragover', function(e) {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
            this.classList.add('kanban-drop-target');

            const afterElement = getDragAfterElement(this, e.clientY);
            if (draggedCard) {
                if (afterElement == null) {
                    this.appendChild(draggedCard);
                } else {
                    this.insertBefore(draggedCard, afterElement);
                }
            }
        });

        column.addEventListener('dragleave', function(e) {
            if (!this.contains(e.relatedTarget)) {
                this.classList.remove('kanban-drop-target');
            }
        });

        column.addEventListener('drop', function(e) {
            e.preventDefault();
            this.classList.remove('kanban-drop-target');

            const newStatus = this.dataset.status;
            const cardIds = Array.from(this.querySelectorAll('.kanban-card')).map(c => parseInt(c.dataset.id));

            // Update server
            fetch('/api/tasks/reorder', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ task_ids: cardIds, status: newStatus }),
            }).then(() => {
                // Update count badges
                document.querySelectorAll('.kanban-column').forEach(col => {
                    const status = col.querySelector('.kanban-cards').dataset.status;
                    const count = col.querySelectorAll('.kanban-card').length;
                    col.querySelector('.kanban-count').textContent = count;
                });
                showToast('Task taşındı');
            });
        });
    });
});

function getDragAfterElement(container, y) {
    const cards = [...container.querySelectorAll('.kanban-card:not(.dragging)')];
    return cards.reduce((closest, child) => {
        const box = child.getBoundingClientRect();
        const offset = y - box.top - box.height / 2;
        if (offset < 0 && offset > closest.offset) {
            return { offset, element: child };
        }
        return closest;
    }, { offset: Number.NEGATIVE_INFINITY }).element;
}
