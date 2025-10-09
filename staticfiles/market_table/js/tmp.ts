const assetsDict = {{ assets_dict }};

const locationGroupSelect = document.getElementById("location_group_select");
const locationSelect = document.getElementById("location_select");
const assetSelect = document.getElementById("asset_select");

function populateDropdowns() {
    const group = locationGroupSelect.value;
    locationSelect.innerHTML = "";
    assetSelect.innerHTML = "";

    // Populate location (currently 1:1 with group)
    const loc = group;
    const optionLoc = document.createElement("option");
    optionLoc.value = loc;
    optionLoc.text = loc;
    optionLoc.selected = true;
    locationSelect.appendChild(optionLoc);

    // Populate assets
    assetsDict[group][loc].forEach(asset => {
        const opt = document.createElement("option");
        opt.value = asset;
        opt.text = asset;
        assetSelect.appendChild(opt);
    });
}

locationGroupSelect.addEventListener("change", populateDropdowns);
populateDropdowns(); // initial population

// Sample chart with random values (replace with real data)
const ctxStocks = document.getElementById('stocksChart').getContext('2d');
const stocksChart = new Chart(ctxStocks, {
    type: 'line',
    data: {
        labels: Array.from({length: 21}, (_, i) => i+1),
        datasets: [{
            label: 'Price',
            data: Array.from({length: 21}, () => Math.random()*100),
            borderColor: 'rgb(54, 162, 235)',
            backgroundColor: 'rgba(54, 162, 235, 0.2)',
        }]
    },
    options: { responsive: true }
});

const ctxYield = document.getElementById('yieldCurveChart').getContext('2d');
const yieldChart = new Chart(ctxYield, {
    type: 'line',
    data: {
        labels: [1,2,3,5,7,10,20,30],
        datasets: [
            {
                label: 'Target Day',
                data: [0.5,1,1.5,2,2.5,3,4,4.5],
                borderColor: 'rgb(255, 99, 132)',
                backgroundColor: 'rgba(255, 99, 132, 0.2)',
            },
            {
                label: 'Previous Day',
                data: [0.4,0.9,1.4,1.9,2.3,2.8,3.9,4.2],
                borderColor: 'rgb(54, 162, 235)',
                backgroundColor: 'rgba(54, 162, 235, 0.2)',
            }
        ]
    },
    options: { responsive: true }
});
