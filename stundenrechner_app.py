import streamlit as st
import pandas as pd
import holidays
import datetime
import time
import plotly.express as px

# ==============================================================================
#  1. FINALE BERECHNUNGSLOGIK MIT RÜCKGABE DER RECHENSCHRITTE
# ==============================================================================
def calculate_project_hours(
    year, state_code, weekly_hours, vacation_days,
    use_sick_leave, sick_leave_rate, use_meetings, meeting_hours_weekly,
    use_buffer, buffer_rate, additional_deductions
):
    """
    Berechnet die planbaren Projektstunden und gibt eine detaillierte Aufschlüsselung
    der Berechnungsschritte für maximale Transparenz zurück.
    """
    # --- Schritt 1: Brutto-Arbeitstage ermitteln ---
    de_holidays = holidays.Germany(prov=state_code, years=year)
    gross_workdays = 0
    holidays_on_workdays = 0
    for day in range(1, 366):
        try:
            current_date = datetime.date(year, 1, 1) + datetime.timedelta(days=day-1)
            if current_date.year == year:
                if current_date.weekday() < 5:
                    if current_date in de_holidays:
                        holidays_on_workdays += 1
                    else:
                        gross_workdays += 1
        except (ValueError, OverflowError):
            continue

    # --- Schritt 2: Netto-Arbeitstage & Stundenbasis ---
    net_workdays = gross_workdays - vacation_days
    if net_workdays < 0: net_workdays = 0
    daily_hours = weekly_hours / 5
    net_hours_before_deductions = net_workdays * daily_hours

    # --- Schritt 3: Variable Abzüge berechnen ---
    sickness_hours = net_hours_before_deductions * (sick_leave_rate / 100.0) if use_sick_leave else 0
    net_work_weeks = net_workdays / 5 if net_workdays > 0 else 0
    meeting_hours_yearly = net_work_weeks * meeting_hours_weekly if use_meetings else 0
    
    base_hours_for_percentage = net_hours_before_deductions - sickness_hours - meeting_hours_yearly

    # --- Schritt 4: Individuelle Abzüge umrechnen ---
    total_additional_hours = 0
    processed_deductions = {}
    additional_deductions_breakdown = []

    for item in additional_deductions:
        name, value, unit = item['name'], item['value'], item['unit']
        hours_year = 0
        if value > 0:
            if unit == 'Stunden / Jahr': hours_year = value
            elif unit == 'Stunden / Woche': hours_year = value * net_work_weeks
            elif unit == '% vom Jahr': hours_year = base_hours_for_percentage * (value / 100.0)
        
        total_additional_hours += hours_year
        if hours_year > 0:
            processed_deductions[name] = processed_deductions.get(name, 0) + hours_year
            additional_deductions_breakdown.append({'name': name, 'hours': hours_year})

    # --- Schritt 5: Finale Berechnung ---
    hours_before_buffer = base_hours_for_percentage - total_additional_hours
    buffer_hours = hours_before_buffer * (buffer_rate / 100.0) if use_buffer else 0
    final_plannable_hours = hours_before_buffer - buffer_hours
    if final_plannable_hours < 0: final_plannable_hours = 0

    # --- Schritt 6: Ergebnisse bündeln ---
    aufteilung = { "Projektarbeit": round(final_plannable_hours) }
    # ... (weitere Einträge für die Aufteilung)
    aufteilung["Urlaub"] = round(vacation_days * daily_hours)
    aufteilung["Feiertage"] = round(holidays_on_workdays * daily_hours)
    if sickness_hours > 0: aufteilung["Krankheit"] = round(sickness_hours)
    if meeting_hours_yearly > 0: aufteilung["Meetings (intern)"] = round(meeting_hours_yearly)
    if buffer_hours > 0: aufteilung["Puffer (unplanbar)"] = round(buffer_hours)
    for name, hours in processed_deductions.items():
        aufteilung[name] = aufteilung.get(name, 0) + round(hours)

    return {
        "metrics": {
            "Planbare Stunden pro Jahr": round(final_plannable_hours),
            "Planbare Stunden pro Monat": round(final_plannable_hours / 12),
            "Planbare Stunden pro Woche": round(final_plannable_hours / net_work_weeks) if net_work_weeks > 0 else 0,
            "Planbare Stunden pro Tag": round(final_plannable_hours / net_workdays) if net_workdays > 0 else 0,
            "Reale Verfügbarkeit in %": round((final_plannable_hours / (gross_workdays * daily_hours)) * 100) if gross_workdays > 0 else 0,
        },
        "aufteilung": aufteilung,
        "calculation_steps": {
            "year": year, "gross_workdays": gross_workdays, "holidays_on_workdays": holidays_on_workdays,
            "vacation_days": vacation_days, "net_workdays": net_workdays, "daily_hours": daily_hours,
            "net_hours_before_deductions": net_hours_before_deductions, "use_sick_leave": use_sick_leave,
            "sick_leave_rate": sick_leave_rate, "sickness_hours": sickness_hours, "use_meetings": use_meetings,
            "meeting_hours_weekly": meeting_hours_weekly, "meeting_hours_yearly": meeting_hours_yearly,
            "additional_deductions_breakdown": additional_deductions_breakdown, "hours_before_buffer": hours_before_buffer,
            "use_buffer": use_buffer, "buffer_rate": buffer_rate, "buffer_hours": buffer_hours,
            "final_plannable_hours": final_plannable_hours
        }
    }

# ==============================================================================
#  2. STREAMLIT BENUTZEROBERFLÄCHE
# ==============================================================================

st.set_page_config(page_title="Kapazitätsrechner | Schübeler Consulting", layout="wide")

if 'additional_deductions' not in st.session_state: st.session_state.additional_deductions = []
if 'deduction_id_counter' not in st.session_state: st.session_state.deduction_id_counter = 0

# --- SEITENLEISTE ---
st.sidebar.image("customcolor_logo_transparent_background.png", use_column_width=True)
st.sidebar.header("Allgemeine Parameter")

bundeslaender = {"BW": "Baden-Württemberg", "BY": "Bayern", "BE": "Berlin", "BB": "Brandenburg", "HB": "Bremen", "HH": "Hamburg", "HE": "Hessen", "MV": "Mecklenburg-Vorpommern", "NI": "Niedersachsen", "NW": "Nordrhein-Westfalen", "RP": "Rheinland-Pfalz", "SL": "Saarland", "SN": "Sachsen", "ST": "Sachsen-Anhalt", "SH": "Schleswig-Holstein", "TH": "Thüringen"}

year = st.sidebar.selectbox("🗓️ Analysejahr", options=range(datetime.date.today().year, datetime.date.today().year + 6), index=0)
state_name = st.sidebar.selectbox("📍 Bundesland", options=list(bundeslaender.values()), index=9)
state_code = [code for code, name in bundeslaender.items() if name == state_name][0]
weekly_hours = st.sidebar.number_input("🕒 Vertragliche Wochenstunden", min_value=10.0, max_value=60.0, value=40.0, step=0.5)
vacation_days = st.sidebar.number_input("🌴 Urlaubstage pro Jahr", min_value=0, max_value=100, value=30, step=1)

st.sidebar.markdown("---")
st.sidebar.header("Variable Zeitabzüge")

use_meetings = st.sidebar.checkbox("Meetings berücksichtigen", value=True)
meeting_hours_weekly = st.sidebar.number_input(" Meeting-Stunden pro Woche", min_value=0.0, max_value=20.0, value=2.5, step=0.5, disabled=not use_meetings)
use_sick_leave = st.sidebar.checkbox("Krankenstand berücksichtigen", value=True)
sick_leave_rate = st.sidebar.slider(" Durchschnittlicher Krankenstand", 0, 20, 8, 1, format="%d%%", disabled=not use_sick_leave)
use_buffer = st.sidebar.checkbox("Puffer für Ungeplantes berücksichtigen", value=True)
buffer_rate = st.sidebar.slider(" Höhe des Puffers", 0, 30, 10, 1, format="%d%%", disabled=not use_buffer)

st.sidebar.markdown("---")
st.sidebar.header("Individuelle Zeitabzüge")

def add_deduction():
    st.session_state.deduction_id_counter += 1
    new_id = st.session_state.deduction_id_counter
    st.session_state.additional_deductions.append({'id': new_id, 'name': f'Faktor {new_id}', 'value': 0.0, 'unit': 'Stunden / Jahr'})
def remove_deduction(item_id):
    st.session_state.additional_deductions = [d for d in st.session_state.additional_deductions if d['id'] != item_id]

for item in st.session_state.additional_deductions:
    item_id = item['id']
    with st.sidebar.expander(f"Individueller Faktor: **{item.get('name', '')}**", expanded=True):
        item['name'] = st.text_input("Bezeichnung", value=item.get('name', ''), key=f"name_{item_id}")
        cols = st.columns([2, 3])
        item['value'] = cols[0].number_input("Wert", min_value=0.0, value=item.get('value', 0.0), key=f"value_{item_id}", step=1.0)
        item['unit'] = cols[1].selectbox("Einheit", options=['Stunden / Jahr', 'Stunden / Woche', '% vom Jahr'], index=['Stunden / Jahr', 'Stunden / Woche', '% vom Jahr'].index(item.get('unit', 'Stunden / Jahr')), key=f"unit_{item_id}")
        st.button("Diesen Faktor entfernen", key=f"del_{item_id}", on_click=remove_deduction, args=(item_id,), use_container_width=True)
st.sidebar.button("➕ Weiteren Faktor hinzufügen", on_click=add_deduction, use_container_width=True)

# --- HAUPTSEITE ---
st.title("⏱️ Interaktiver Kapazitätsrechner")

if 'results' not in st.session_state: st.session_state.results = None
if st.sidebar.button("Jetzt berechnen", type="primary", use_container_width=True, key="calculate_main"):
    st.session_state.results = calculate_project_hours(
        year, state_code, weekly_hours, vacation_days, use_sick_leave, sick_leave_rate,
        use_meetings, meeting_hours_weekly, use_buffer, buffer_rate, st.session_state.additional_deductions)
    st.session_state.year = year

if st.session_state.results:
    results, aufteilung, steps = st.session_state.results['metrics'], st.session_state.results['aufteilung'], st.session_state.results['calculation_steps']
    display_year = st.session_state.get('year', year)
    
    st.subheader(f"Ergebnis für das Jahr {display_year}")
    cols = st.columns(5)
    cols[0].metric("Pro Jahr", f"{results['Planbare Stunden pro Jahr']} h")
    cols[1].metric("Pro Monat", f"{results['Planbare Stunden pro Monat']} h")
    cols[2].metric("Pro Woche", f"{results['Planbare Stunden pro Woche']} h")
    cols[3].metric("Pro Tag", f"{results['Planbare Stunden pro Tag']} h", help=f"Basiert auf {steps['net_workdays']} Netto-Arbeitstagen.")
    cols[4].metric("Reale Verfügbarkeit", f"{results['Reale Verfügbarkeit in %']}%")

    st.markdown("---")

    col_chart, col_data = st.columns([3, 2])
    with col_chart:
        st.subheader("Verteilung der Jahresarbeitszeit")
        aufteilung_df = pd.DataFrame.from_dict(aufteilung, orient='index', columns=['Stunden']).reset_index().rename(columns={'index': 'Aktivität'}).sort_values('Stunden', ascending=False)
        color_map = {'Projektarbeit': '#04002D', 'Urlaub': '#00A0C6', 'Feiertage': '#9FD5E2', 'Krankheit': '#6c757d', 'Meetings (intern)': '#adb5bd', 'Puffer (unplanbar)': '#dee2e6'}
        for activity in aufteilung_df['Aktivität']:
            if activity not in color_map: color_map[activity] = '#343a40'
        fig = px.bar(aufteilung_df, x='Aktivität', y='Stunden', title=f"Gesamte Brutto-Jahresstunden: {sum(aufteilung.values())}", color='Aktivität', color_discrete_map=color_map)
        fig.update_traces(texttemplate='%{y:.0f}', textposition='outside')
        fig.update_layout(showlegend=False, xaxis_title=None, yaxis_title="Stunden pro Jahr", margin=dict(t=50)) # BUGFIX: Rand oben hinzugefügt
        st.plotly_chart(fig, use_container_width=True)

    with col_data:
        st.subheader("Daten im Detail")
        display_df = aufteilung_df[aufteilung_df['Stunden'] > 0]
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        csv = display_df.to_csv(index=False).encode('utf-8-sig') # BUGFIX: Kodierung für korrekte Umlaute
        st.download_button("Daten als CSV exportieren", csv, f'kapazitaetsplanung_{display_year}_{state_name}.csv', 'text/csv', use_container_width=True)
    
    st.markdown("---")

    # NEU: Transparente Darstellung des Rechenwegs
    with st.expander("Wie wird das berechnet? (Rechenweg anzeigen)"):
        st.markdown(f"""
        Die Berechnung Ihrer planbaren Projektstunden erfolgt nachvollziehbar in mehreren Schritten. 
        Hier ist die detaillierte Aufschlüsselung basierend auf Ihren Eingaben für das Jahr **{steps['year']}**:

        **1. Ermittlung der Netto-Arbeitstage**
        - Arbeitstage im Jahr (Mo-Fr, ohne Feiertage): `{steps['gross_workdays']}`
        - Abzüglich Ihrer Angabe für Urlaubstage: ` - {steps['vacation_days']}`
        - **Netto verfügbare Arbeitstage:** `= {steps['net_workdays']} Tage`

        **2. Umrechnung in verfügbare Stunden (Basis)**
        - Netto-Arbeitstage multipliziert mit den täglichen Vertragsstunden ({steps['daily_hours']:.2f} h):
        - **Netto verfügbare Stunden (vor Abzügen):** `= {steps['net_hours_before_deductions']:.1f} h`

        **3. Abzug der variablen Faktoren**
        - Abzüglich Krankenstand ({steps['sick_leave_rate']}% von der Stundenbasis): ` - {steps['sickness_hours']:.1f} h`
        - Abzüglich interner Meetings ({steps['meeting_hours_weekly']} h/Woche): ` - {steps['meeting_hours_yearly']:.1f} h`
        """)
        if steps['additional_deductions_breakdown']:
            st.markdown("- **Abzüglich Ihrer individuellen Faktoren:**")
            for item in steps['additional_deductions_breakdown']:
                st.markdown(f"  - *{item['name']}*: ` - {item['hours']:.1f} h`")
        st.markdown(f"""
        - **Verfügbare Stunden vor Puffer:** `= {steps['hours_before_buffer']:.1f} h`

        **4. Finale Berechnung mit Puffer**
        - Abzüglich des Puffers für Ungeplantes ({steps['buffer_rate']}% vom Zwischenergebnis): ` - {steps['buffer_hours']:.1f} h`
        - ### **Planbare Projektstunden pro Jahr:** `= {steps['final_plannable_hours']:.1f} h`
        """)

    st.markdown("---")
    st.warning("Die hier dargestellten Werte stellen eine Jahreshochrechnung dar. Monatliche und wöchentliche Werte sind mathematische Durchschnittswerte und berücksichtigen keine saisonalen Schwankungen. Für eine detaillierte, monatsspezifische Planung empfehlen wir, diese Ergebnisse als strategische Grundlage zu verwenden.")

else:
    st.info("Bitte passen Sie die Parameter in der linken Seitenleiste an und klicken Sie auf **'Jetzt berechnen'**.")