import io
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from typing import List, Tuple

def generate_pie_chart(data: List[Tuple[str, float]], title: str) -> io.BytesIO:
    """
    Generate a pie chart from data.
    
    Args:
        data: List of (category_name, amount) tuples
        title: Chart title
        
    Returns:
        BytesIO object containing image data
    """
    if not data:
        return None
        
    # Separate labels and values
    labels = [item[0] for item in data]
    sizes = [item[1] for item in data]
    
    # Create figure
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Color palette
    colors = plt.cm.Pastel1(range(len(data)))
    
    # Plot
    wedges, texts, autotexts = ax.pie(
        sizes, 
        labels=labels, 
        autopct='%1.1f%%',
        startangle=90,
        colors=colors,
        pctdistance=0.85,
        explode=[0.05] * len(data)  # Slight explode for all slices
    )
    
    # Draw circle for donut chart look
    centre_circle = plt.Circle((0,0),0.70,fc='white')
    fig.gca().add_artist(centre_circle)
    
    # Styling
    plt.setp(autotexts, size=8, weight="bold")
    plt.setp(texts, size=9)
    
    ax.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle
    plt.title(title, pad=20, fontsize=14, fontweight='bold')
    
    # Save to buffer
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
    buf.seek(0)
    plt.close(fig)
    
    return buf

def generate_bar_chart(
    data: List[Tuple[str, float]], 
    title: str,
    x_label: str = "",
    y_label: str = "VNĐ"
) -> io.BytesIO:
    """
    Generate a bar chart.
    
    Args:
        data: List of (label, value) tuples
        title: Chart title
        
    Returns:
        BytesIO object containing image data
    """
    if not data:
        return None
        
    labels = [item[0] for item in data]
    values = [item[1] for item in data]
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Create bars
    bars = ax.bar(labels, values, color='skyblue', width=0.6)
    
    # Add values on top of bars
    for bar in bars:
        height = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width()/2.,
            height,
            f'{height:,.0f}',
            ha='center', va='bottom',
            fontsize=8
        )
            
    # Styling
    ax.set_title(title, pad=20, fontsize=14, fontweight='bold')
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    
    # Format Y axis as currency
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, p: format(int(x), ',')))
    
    plt.xticks(rotation=45, ha='right')
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    
    # Save
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
    buf.seek(0)
    plt.close(fig)
    
    return buf
