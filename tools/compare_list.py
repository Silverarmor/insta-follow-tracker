list_a = ['Apple', 'Banana', 'Canteloupe']
list_b = ['Apple', 'Banana', 'Delta']

print(list((set(list_a) - set(list_b))))
# --> ['Canteloupe']

# print("These items are not in both lists: " missing_items_var)