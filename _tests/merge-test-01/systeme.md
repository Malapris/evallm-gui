GOAL:
Merge the following JSON objects into a single JSON by merging each values separated by '|' and avoid duplicate values.
For similar values, try to find a synthesis between them, otherwise concatenate the values with '|' as a separator.
You must absolutely respect the OUTPUT JSON FORMAT .
ALL JSON OBJECTS ARE VALID AND REPRESENT THE VERY SAME CONTEST.
IMPORTANT : Return only the merged JSON, without introductions, comments or explanations.
Return only one JSON, nothing else. Do not return a list, return only one JSON.

OUTPUT JSON FORMAT you must respect absolutely (key:meaning) :
[ {
    "Titre": "the contest title. You must summarize the different values in one with all the details.",
    "Type": "summarize the type of contest (example: photo, drawing, painting, etc.). Give a precise list of keywords separated by commas.",
    "Organisateur": "summarize the name of the contest organizer with their nationality, location, private or public.",
    "Description": "summarize, without considering tone, all the interesting informations about how the contest works, the best points and the worse.",
    "Description_originale": "complete and original description of the contest without translation or summary.",
    "Images": "untouched complete URLs of images associated with the contest, separated by '|'. Only take those related to the contest!",
    "Theme": "summarize the theme of the contest (example: portrait, human, nature, animals, artistic, etc.), there can be multiple separated by '|'.",
    "Portee": "The scope of the contest with a score from 0 to 10 where 10 is maximum, meaning the interest in participating with the visibility/notoriety it can bring and the prizes it offers.",
    "Prix": "the list prizes to be won with this contest (money, gifts, internship, etc.). If it's money you give the amount directly. If there are several, you make a list with separation by commas.",
    "Eligibilite": "list the terms and conditions for participating in the contest (particularly check nationality, age, location and gender), separated by commas.",
    "Date": "the deadline for contest participation in Year/Month/Day format (example: 2025/12/31). If you don't have the information, don't put the date. If you have the the due date (last day to participate) : put ONLY this one !",
    "Selection": "summarize how the selection process works: jury or vote or others.",
    "Frais": "participation or registration fees for the contest. If you have the amount put it with the currency, if you just know it's paid, put 'Paid'. If there are several amounts, separate them with '|'.",
    "URL": "untouched links associated with the contest, they must be separated by '|', keep them intact."
} ]
